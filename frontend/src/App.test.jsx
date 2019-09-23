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

import React from "react"
import ReactDOM from "react-dom"
import { SessionInfo } from "./lib/SessionInfo"
import { MetricsManager } from "./lib/MetricsManager"
import { getMetricsManagerForTest } from "./lib/MetricsManagerTestUtils"
import App from "./App"

beforeEach(() => {
  SessionInfo.current = new SessionInfo({
    streamlitVersion: "sv",
    installationId: "iid",
    authorEmail: "ae",
  })
  MetricsManager.current = getMetricsManagerForTest()
})

afterEach(() => {
  SessionInfo["singleton"] = null
})

it("renders without crashing", () => {
  const mountPoint = document.createElement("div")
  mountPoint.setAttribute("id", "ConnectionStatus")
  document.body.appendChild(mountPoint)
  ReactDOM.render(<App />, mountPoint)
  ReactDOM.unmountComponentAtNode(mountPoint)
})
