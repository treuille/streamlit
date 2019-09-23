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

import React, { PureComponent, ReactNode } from "react"
import { List, Map as ImmutableMap } from "immutable"
import classNames from "classnames"

import Block from "components/core/Block/"
import { ReportRunState } from "lib/ReportRunState"
import { WidgetStateManager } from "lib/WidgetStateManager"

import { ThemeProvider } from "baseui"
import { widgetTheme } from "lib/widgetTheme"
import "./ReportView.scss"
import "./Widget.scss"

type SimpleElement = ImmutableMap<string, any>
type Element = SimpleElement | BlockElement
interface BlockElement extends List<Element> {}

interface Elements {
  main: BlockElement
  sidebar: BlockElement
}

interface Props {
  elements: Elements

  // The unique ID for the most recent run of the report.
  reportId: string

  reportRunState: ReportRunState

  /**
   * If true, "stale" elements (that is, elements that were created during a previous
   * run of a currently-running report) will be faded out.
   *
   * (When we're viewing a shared report, this is set to false.)
   */
  showStaleElementIndicator: boolean

  widgetMgr: WidgetStateManager

  // Disable the widgets when not connected to the server.
  widgetsDisabled: boolean

  // Wide mode
  wide: boolean
}

/**
 * Renders a Streamlit report. Reports consist of 0 or more elements.
 */
class ReportView extends PureComponent<Props> {
  private hasSidebar = (): boolean => !this.props.elements.sidebar.isEmpty()

  public render = (): ReactNode => {
    const reportViewClassName = classNames("reportview-container", {
      "--wide": this.props.wide,
      "--with-sidebar": this.hasSidebar(),
    })

    return (
      <ThemeProvider theme={widgetTheme}>
        <div className={reportViewClassName}>
          {this.hasSidebar() && (
            <section className="sidebar">
              <div className="block-container">
                <Block
                  elements={this.props.elements.sidebar}
                  reportId={this.props.reportId}
                  reportRunState={this.props.reportRunState}
                  showStaleElementIndicator={
                    this.props.showStaleElementIndicator
                  }
                  widgetMgr={this.props.widgetMgr}
                  widgetsDisabled={this.props.widgetsDisabled}
                />
              </div>
            </section>
          )}
          <section className="main">
            <div className="block-container">
              <Block
                elements={this.props.elements.main}
                reportId={this.props.reportId}
                reportRunState={this.props.reportRunState}
                showStaleElementIndicator={
                  this.props.showStaleElementIndicator
                }
                widgetMgr={this.props.widgetMgr}
                widgetsDisabled={this.props.widgetsDisabled}
              />
            </div>
          </section>
        </div>
      </ThemeProvider>
    )
  }
}

export default ReportView
