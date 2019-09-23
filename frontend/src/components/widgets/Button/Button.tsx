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
import { Button as UIButton } from "baseui/button"
import { Map as ImmutableMap } from "immutable"
import { WidgetStateManager } from "lib/WidgetStateManager"
import { buttonOverrides } from "lib/widgetTheme"

interface Props {
  disabled: boolean
  element: ImmutableMap<string, any>
  widgetMgr: WidgetStateManager
  width: number
}

class Button extends React.PureComponent<Props> {
  private handleClick = () => {
    const widgetId = this.props.element.get("id")
    this.props.widgetMgr.setTriggerValue(widgetId)
  }

  public render(): React.ReactNode {
    const label = this.props.element.get("label")
    const style = { width: this.props.width }

    return (
      <div className="Widget row-widget stButton" style={style}>
        {/*
        // @ts-ignore */}
        <UIButton
          overrides={buttonOverrides}
          onClick={this.handleClick}
          disabled={this.props.disabled}
        >
          {label}
        </UIButton>
      </div>
    )
  }
}

export default Button
