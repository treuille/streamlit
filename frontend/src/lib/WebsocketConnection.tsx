/**
 * @license
 * Copyright 2018-2019 Streamlit Inc.
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *    http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

import React, { Fragment } from "react"
import Resolver from "lib/Resolver"
import { SessionInfo } from "lib/SessionInfo"
import { ConnectionState } from "lib/ConnectionState"
import { ForwardMsg, BackMsg, IBackMsg } from "autogen/proto"
import { logMessage, logWarning, logError } from "lib/log"

/**
 * Name of the logger.
 */
const LOG = "WebsocketConnection"

/**
 * The path where we should ping (via HTTP) to see if the server is up.
 */
const SERVER_PING_PATH = "healthz"

/**
 * Wait this long between pings, in millis.
 */
const PING_RETRY_PERIOD_MS = 500

/**
 * Timeout when attempting to connect to a websocket, in millis.
 * This should be <= bootstrap.py#BROWSER_WAIT_TIMEOUT_SEC.
 */
const WEBSOCKET_TIMEOUT_MS = 1000

/**
 * If the ping retrieves a 403 status code a message will be displayed.
 * This constant is the link to the documentation.
 */
const CORS_ERROR_MESSAGE_DOCUMENTATION_LINK =
  "https://developer.mozilla.org/en-US/docs/Web/HTTP/CORS"

interface BaseUriParts {
  host: string
  port: number
}

type OnMessage = (ForwardMsg: any) => void
type OnConnectionStateChange = (connectionState: ConnectionState) => void
type OnRetry = (totalTries: number, errorNode: React.ReactNode) => void

interface Args {
  /**
   * List of URLs to connect to. We'll try the first, then the second, etc. If
   * all fail, we'll retry from the top. The number of retries depends on
   * whether this is a local connection.
   */
  baseUriPartsList: BaseUriParts[]

  /**
   * Function called when our ConnectionState changes.
   * If the new ConnectionState is ERROR, errMsg will be defined.
   */
  onConnectionStateChange: OnConnectionStateChange

  /**
   * Function called every time we ping the server for sign of life.
   */
  onRetry: OnRetry

  /**
   * Function called when we receive a new message.
   */
  onMessage: OnMessage
}

interface MessageQueue {
  [index: number]: any
}

/**
 * Events of the WebsocketConnection state machine. Here's what the FSM looks
 * like:
 *
 *   INITIAL
 *     │
 *     │               on conn succeed
 *     v               :
 *   CONNECTING ───────────────> CONNECTED
 *     │  ^                          │
 *     │  │:on ping succeed          │
 *     │:on timeout/error/closed     │
 *     v  │                          │:on error/closed
 *   PINGING_SERVER <────────────────┘
 */
type Event =
  | "INITIALIZED"
  | "CONNECTION_CLOSED"
  | "CONNECTION_ERROR"
  | "CONNECTION_WTF"
  | "CONNECTION_SUCCEEDED"
  | "CONNECTION_TIMED_OUT"
  | "SERVER_PING_SUCCEEDED"

/**
 * This class is the "brother" of StaticConnection. The class connects to the
 * server and gets deltas over a websocket connection.
 */
export class WebsocketConnection {
  private readonly args: Args

  /**
   * Index to the URI in uriList that we're going to try to connect to.
   */
  private uriIndex = 0

  /**
   * To guarantee packet transmission order, this is the index of the last
   * dispatched incoming message.
   */
  private lastDispatchedMessageIndex = -1

  /**
   * And this is the index of the next message we recieve.
   */
  private nextMessageIndex = 0

  /**
   * This dictionary stores recieved messages that we haven't sent out yet
   * (because we're still decoding previous messages)
   */
  private messageQueue: MessageQueue = {}

  /**
   * The current state of this object's state machine.
   */
  private state = ConnectionState.INITIAL

  /**
   * The WebSocket object we're connecting with.
   */
  private websocket?: WebSocket | null

  /**
   * WebSocket objects don't support retries, so we have to implement them
   * ourselves. We use setTimeout to wait for a connection and retry once the
   * timeout fire. This is the timer ID from setTimeout, so we can cancel it if
   * needed.
   */
  private wsConnectionTimeoutId?: number | null

  public constructor(args: Args) {
    this.args = args
    this.stepFsm("INITIALIZED")
  }

  // This should only be called inside stepFsm().
  private setFsmState(state: ConnectionState): void {
    logMessage(LOG, `New state: ${state}`)
    this.state = state
    this.args.onConnectionStateChange(state)

    // Perform actions when entering certain states.
    switch (this.state) {
      case ConnectionState.PINGING_SERVER:
        this.pingServer()
        break

      case ConnectionState.CONNECTING:
        this.connectToWebSocket()
        break

      case ConnectionState.CONNECTED:
      case ConnectionState.INITIAL:
      default:
        break
    }
  }

  private stepFsm(event: Event): void {
    logMessage(LOG, `State: ${this.state}; Event: ${event}`)

    // Anything combination of state+event that is not explicitly called out
    // below is illegal and raises an error.

    switch (this.state) {
      case ConnectionState.INITIAL:
        if (event === "INITIALIZED") {
          this.setFsmState(ConnectionState.CONNECTING)
          return
        }
        break

      case ConnectionState.CONNECTING:
        if (event === "CONNECTION_SUCCEEDED") {
          this.setFsmState(ConnectionState.CONNECTED)
          return
        } else if (
          event === "CONNECTION_TIMED_OUT" ||
          event === "CONNECTION_ERROR" ||
          event === "CONNECTION_CLOSED"
        ) {
          this.setFsmState(ConnectionState.PINGING_SERVER)
          return
        }
        break

      case ConnectionState.CONNECTED:
        if (event === "CONNECTION_CLOSED" || event === "CONNECTION_ERROR") {
          this.setFsmState(ConnectionState.PINGING_SERVER)
          return
        }
        break

      case ConnectionState.PINGING_SERVER:
        if (event === "SERVER_PING_SUCCEEDED") {
          this.setFsmState(ConnectionState.CONNECTING)
          return
        }
        break

      default:
        break
    }

    throw new Error(
      "Unsupported state transition.\n" +
        `State: ${this.state}\n` +
        `Event: ${event}`
    )
  }

  private async pingServer(): Promise<void> {
    const uris = this.args.baseUriPartsList.map((_, i) =>
      buildHttpUri(this.args.baseUriPartsList[i], SERVER_PING_PATH)
    )

    this.uriIndex = await doHealthPing(
      uris,
      PING_RETRY_PERIOD_MS,
      this.args.onRetry
    )

    this.stepFsm("SERVER_PING_SUCCEEDED")
  }

  private connectToWebSocket(): void {
    const uri = buildWsUri(this.args.baseUriPartsList[this.uriIndex])

    if (this.websocket != null) {
      // This should never happen. We set the websocket to null in both FSM
      // nodes that lead to this one.
      throw new Error("Websocket already exists")
    }

    logMessage(LOG, "creating WebSocket")
    this.websocket = new WebSocket(uri)

    this.setConnectionTimeout(uri)

    const localWebsocket = this.websocket

    const checkWebsocket = (): boolean => {
      return localWebsocket === this.websocket
    }

    this.websocket.onmessage = (event: MessageEvent) => {
      if (checkWebsocket()) {
        this.handleMessage(event.data)
      }
    }

    this.websocket.onopen = () => {
      if (checkWebsocket()) {
        logMessage(LOG, "WebSocket onopen")
        this.stepFsm("CONNECTION_SUCCEEDED")
      }
    }

    this.websocket.onclose = () => {
      if (checkWebsocket()) {
        logMessage(LOG, "WebSocket onclose")
        this.cancelConnectionAttempt()
        this.stepFsm("CONNECTION_CLOSED")
      }
    }

    this.websocket.onerror = () => {
      if (checkWebsocket()) {
        logMessage(LOG, "WebSocket onerror")
        this.cancelConnectionAttempt()
        this.stepFsm("CONNECTION_ERROR")
      }
    }
  }

  private setConnectionTimeout(uri: string): void {
    if (this.wsConnectionTimeoutId != null) {
      // This should never happen. We set the timeout ID to null in both FSM
      // nodes that lead to this one.
      throw new Error("WS timeout is already set")
    }

    const localWebsocket = this.websocket

    this.wsConnectionTimeoutId = window.setTimeout(() => {
      if (localWebsocket !== this.websocket) {
        return
      }

      if (this.wsConnectionTimeoutId == null) {
        // Sometimes the clearTimeout doesn't work. No idea why :-/
        logWarning(LOG, "Timeout fired after cancellation")
        return
      }

      if (this.websocket == null) {
        // This should never happen! The only place we call
        // setConnectionTimeout() should be immediately before setting
        // this.websocket.
        this.cancelConnectionAttempt()
        this.stepFsm("CONNECTION_WTF")
        return
      }

      if (this.websocket.readyState === 0 /* CONNECTING */) {
        logMessage(LOG, `${uri} timed out`)
        this.cancelConnectionAttempt()
        this.stepFsm("CONNECTION_TIMED_OUT")
      }
    }, WEBSOCKET_TIMEOUT_MS)
    logMessage(LOG, `Set WS timeout ${this.wsConnectionTimeoutId}`)
  }

  private cancelConnectionAttempt(): void {
    // Need to make sure the websocket is closed in the same function that
    // cancels the connection timer. Otherwise, due to javascript's concurrency
    // model, when the onclose event fires it can get handled in between the
    // two functions, causing two events to be sent to the FSM: a
    // CONNECTION_TIMED_OUT and a CONNECTION_ERROR.

    if (this.websocket) {
      this.websocket.close()
      this.websocket = null
    }

    if (this.wsConnectionTimeoutId != null) {
      logMessage(LOG, `Clearing WS timeout ${this.wsConnectionTimeoutId}`)
      window.clearTimeout(this.wsConnectionTimeoutId)
      this.wsConnectionTimeoutId = null
    }
  }

  /**
   * Encodes the message with the outgoingMessageType and sends it over the
   * wire.
   */
  public sendMessage(obj: IBackMsg): void {
    if (!this.websocket) {
      return
    }
    const msg = BackMsg.create(obj)
    const buffer = BackMsg.encode(msg).finish()
    this.websocket.send(buffer)
  }

  private handleMessage(data: any): void {
    // Assign this message an index.
    const messageIndex = this.nextMessageIndex
    this.nextMessageIndex += 1

    // Read in the message data.
    const reader = new FileReader()
    reader.readAsArrayBuffer(data)
    reader.onloadend = () => {
      if (this.messageQueue == null) {
        logError(LOG, "No message queue.")
        return
      }

      const result = reader.result
      if (result == null || typeof result === "string") {
        logError(LOG, `Unexpected result from FileReader: ${result}.`)
        return
      }

      const resultArray = new Uint8Array(result)
      this.messageQueue[messageIndex] = ForwardMsg.decode(resultArray)
      while (this.lastDispatchedMessageIndex + 1 in this.messageQueue) {
        const dispatchMessageIndex = this.lastDispatchedMessageIndex + 1
        this.args.onMessage(this.messageQueue[dispatchMessageIndex])
        delete this.messageQueue[dispatchMessageIndex]
        this.lastDispatchedMessageIndex = dispatchMessageIndex
      }
    }
  }
}

function buildWsUri({ host, port }: BaseUriParts): string {
  const protocol = window.location.href.startsWith("https://") ? "wss" : "ws"
  return `${protocol}://${host}:${port}/stream`
}

function buildHttpUri({ host, port }: BaseUriParts, path: string): string {
  return `//${host}:${port}/${path}`
}

/**
 * Attempts to connect to the URIs in uriList (in round-robin fashion) and
 * retries forever until one of the URIs responds with 'ok'.
 * Returns a promise with the index of the URI that worked.
 */
function doHealthPing(
  uriList: string[],
  timeoutMs: number,
  retryCallback: OnRetry
): Promise<number> {
  const resolver = new Resolver<number>()
  let totalTries = 0
  let uriNumber = 0
  let tryTimestamp = Date.now()

  // Hoist the connect() declaration.
  let connect = (): void => {}

  const retryImmediately = (): void => {
    uriNumber++
    if (uriNumber >= uriList.length) {
      uriNumber = 0
    }

    connect()
  }

  // Make sure we don't retry faster than timeoutMs. This is required because
  // in some cases things fail very quickly, and all our fast retries end up
  // bogging down the browser.
  const retry = (errorNode: React.ReactNode): void => {
    const tryDuration = (Date.now() - tryTimestamp) / 1000
    const retryTimeout = tryDuration < timeoutMs ? timeoutMs - tryDuration : 0

    retryCallback(totalTries, errorNode)

    window.setTimeout(retryImmediately, retryTimeout)
  }

  // Using XHR because it supports timeouts.
  // The location of this declaration matters, as XMLHttpRequests can lead to a
  // memory leak when initialized inside a callback. See
  // https://stackoverflow.com/a/40532229 for more info.
  const xhr = new XMLHttpRequest()

  xhr.timeout = timeoutMs

  const retryWhenTheresNoResponse = (): void => {
    const uri = uriList[uriNumber]

    if (uri.startsWith("//localhost:")) {
      const scriptname =
        SessionInfo.isSet() && SessionInfo.current.commandLine.length
          ? SessionInfo.current.commandLine[0]
          : "yourscript.py"

      retry(
        <Fragment>
          <p>
            Is Streamlit still running? If you accidentally stopped Streamlit,
            just restart it in your terminal:
          </p>
          <pre>
            <code className="bash">streamlit run {scriptname}</code>
          </pre>
        </Fragment>
      )
    } else {
      retry("Connection failed with status 0.")
    }
  }

  const retryWhenIsForbidden = (): void => {
    retry(
      <Fragment>
        <p>Cannot connect to Streamlit (HTTP status: 403).</p>
        <p>
          If you are trying to access a Streamlit app running on another
          server, this could be due to the app's{" "}
          <a href={CORS_ERROR_MESSAGE_DOCUMENTATION_LINK}>CORS</a> settings.
        </p>
      </Fragment>
    )
  }

  xhr.onreadystatechange = () => {
    if (xhr.readyState !== /* DONE */ 4) {
      return
    }

    if (xhr.responseText === "ok") {
      resolver.resolve(uriNumber)
    } else if (xhr.status === /* NO RESPONSE */ 0) {
      retryWhenTheresNoResponse()
    } else if (xhr.status === 403) {
      retryWhenIsForbidden()
    } else {
      retry(
        `Connection failed with status ${xhr.status}, ` +
          `and response "${xhr.responseText}".`
      )
    }
  }

  xhr.ontimeout = e => {
    retry("Connection timed out.")
  }

  connect = () => {
    const uri = uriList[uriNumber]
    logMessage(LOG, `Attempting to connect to ${uri}.`)
    tryTimestamp = Date.now()
    xhr.open("GET", uri, true)

    if (uriNumber === 0) {
      totalTries++
    }

    xhr.send(null)
  }

  connect()

  return resolver.promise
}
