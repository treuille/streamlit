# -*- coding: utf-8 -*-
# Copyright 2018-2019 Streamlit Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""A "Hello World" app."""
from __future__ import division

import streamlit as st
import inspect
from collections import OrderedDict
import urllib

def intro():
    st.markdown(
        """
## Intro...

text text text text text text text text text text text text text text text text
text text text text text text text text text text text text text text text text
text text text text text text text text text text text text text text text text
text text text text text text text text text text text text text text text text
text text text text text text text text text text text text text text text text
text text text text text text text text text text text text text text text text
"""
    )


def mapping_demo():
    """
    This demo shows how to use
    [`st.deck_gl_chart`](https://streamlit.io/docs/api.html#streamlit.deck_gl_chart)
    to display geospatial data.
    """
    import pandas as pd
    import copy, os
    from collections import OrderedDict

    @st.cache
    def from_data_file(filename):
        GITHUB_DATA = "https://raw.githubusercontent.com/streamlit/streamlit/develop/examples/"
        return pd.read_json(os.path.join(GITHUB_DATA, "data", filename))

    ALL_LAYERS = {
        "Bike Rentals": {
            "type": "HexagonLayer",
            "data": from_data_file("bike_rental_stats.json"),
            "radius": 200,
            "elevationScale": 4,
            "elevationRange": [0, 1000],
            "pickable": True,
            "extruded": True,
        },
        "Bart Stop Exits": {
            "type": "ScatterplotLayer",
            "data": from_data_file("bart_stop_stats.json"),
            "radiusScale": 0.05,
            "getRadius": "exits",
        },
        "Bart Stop Names": {
            "type": "TextLayer",
            "data": from_data_file("bart_stop_stats.json"),
            "getText": "name",
            "getColor": [0, 0, 0, 200],
            "getSize": 15,
        },
        "Outbound Flow": {
            "type": "ArcLayer",
            "data": from_data_file("bart_path_stats.json"),
            "pickable": True,
            "autoHighlight": True,
            "getStrokeWidth": 10,
            "widthScale": 0.0001,
            "getWidth": "outbound",
            "widthMinPixels": 3,
            "widthMaxPixels": 30,
        }
    }

    st.sidebar.markdown('### Map Layers')
    selected_layers = [layer for layer_name, layer in ALL_LAYERS.items()
        if st.sidebar.checkbox(layer_name, True)]
    if selected_layers:
        viewport={"latitude": 37.76, "longitude": -122.4, "zoom": 11, "pitch": 50}
        st.deck_gl_chart(viewport=viewport, layers=selected_layers)
    else:
        st.error("Please choose at least one layer above.")

def fractal_demo():
    """
    This app shows how you can use Streamlit to build cool animations.
    It displays an animated fractal based on the the Julia Set. Use the slider
    to tune the level of detail.
    """
    import numpy as np

    iterations = st.sidebar.slider("Level of detail", 1, 100, 70, 1)
    separation = st.sidebar.slider('Separation', 0.7, 2.0, 0.7885)

    m, n, s = 480, 320, 200
    x = np.linspace(-m / s, m / s, num=m).reshape((1, m))
    y = np.linspace(-n / s, n / s, num=n).reshape((n, 1))
    image = st.empty()

    progress_bar = st.sidebar.progress(0)
    frame_text = st.sidebar.empty()
    for frame_num, a in enumerate(np.linspace(0.0, 4 * np.pi, 100)):
        progress_bar.progress(frame_num)
        frame_text.text('Frame %i/100' % (frame_num + 1))
        c = separation * np.exp(1j * a)
        Z = np.tile(x, (n, 1)) + 1j * np.tile(y, (1, m))
        C = np.full((n, m), c)
        M = np.full((n, m), True, dtype=bool)
        N = np.zeros((n, m))

        for i in range(iterations):
            Z[M] = Z[M] * Z[M] + C[M]
            M[np.abs(Z) > 2] = False
            N[M] = i

        image.image(1.0 - (N / N.max()), use_column_width=True)
    progress_bar.empty()
    frame_text.empty()
    st.button("Re-run")

def plotting_demo():
    """
    This demo illustrates a combination of plotting and animation with Streamlit.
    We're generating a bunch of random numbers in a loop for around 10 seconds.
    Enjoy!.
    """
    import time
    import numpy as np

    progress_bar = st.sidebar.progress(0)
    status_text = st.sidebar.empty()
    last_rows = np.random.randn(1, 1)
    chart = st.line_chart(last_rows)
    for i in range(1, 101):
        new_rows = last_rows[-1,:] + np.random.randn(5, 1).cumsum(axis=0)
        status_text.text("%i%% Complete" % i)
        chart.add_rows(new_rows)
        progress_bar.progress(i)
        last_rows = new_rows
        time.sleep(0.05)
    progress_bar.empty()
    st.button("Re-run")

def data_frame_demo():
    """
    This demo shows how to use `st.write` to visualize Pandas DataFrames.

    (Data courtesy of the [UN Data Exlorer](http://data.un.org/Explorer.aspx).)
    """
    import sys
    import pandas as pd
    if sys.version_info[0] < 3:
        reload(sys)
        sys.setdefaultencoding("utf-8")

    @st.cache
    def get_UN_data():
        AWS_BUCKET_URL = "https://streamlit-demo-data.s3-us-west-2.amazonaws.com"
        df = pd.read_csv(AWS_BUCKET_URL + "/agri.csv.gz")
        return df.set_index("Region")

    try:
        df = get_UN_data()
    except urllib.error.URLError:
        st.error("Connection Error. This demo requires internet access")
        return

    countries = st.multiselect("Choose countries", list(df.index),
                               ["China", "United States of America"])
    if not countries:
        st.error("Please select at least one country.")
        return

    "### Gross Agricultural Production \[$1B\]"
    st.write(df.loc[countries].sort_index())

    ax = df.loc[countries].T.plot(kind="area", figsize=(20, 8), stacked=False)
    ax.set_ylabel("GAP in Billions (Int $)", fontsize=25)
    ax.set_xlabel("Year", fontsize=25)
    ax.tick_params(labelsize=20)
    ax.legend(loc=2, prop={"size": 20})
    st.pyplot()


DEMOS = OrderedDict({
    "---": intro,
    "Mapping Demo": mapping_demo,
    "Animation Demo": fractal_demo,
    "DataFrame Demo": data_frame_demo,
    "Plotting Demo": plotting_demo,
})

def run():
    demo_name = st.sidebar.selectbox("Choose a demo", list(DEMOS.keys()), 0)
    demo = DEMOS[demo_name]

    if demo_name != "---":
        show_code = st.sidebar.checkbox("Show code", True)
        st.markdown("# %s" % demo_name)
        st.write(inspect.getdoc(demo))
        demo()
        if show_code:
            st.markdown("## Code")
            sourcelines, n_lines = inspect.getsourcelines(demo)
            sourcelines = reset_indentation(remove_docstring(sourcelines))
            st.code("".join(sourcelines))
    else:
        st.title("Welcome to Streamlit!")
        st.write(
            """
            Streamlit is the best way to create bespoke apps.
            """
        )
        demo()


# This function parses the lines of a function and removes the docstring
# if found. If no docstring is found, it returns None.
def remove_docstring(lines):
    if len(lines) < 3 and '"""' not in lines[1]:
        return lines
    #  lines[2] is the first line of the docstring, past the inital """
    index = 2
    while '"""' not in lines[index]:
        index += 1
        # limit to ~100 lines, if the docstring is longer, just bail
        if index > 100:
            return lines
    # lined[index] is the closing """
    return lines[index + 1:]


# This function remove the common leading indentation from a code block
def reset_indentation(lines):
    if len(lines) == 0:
        return []
    spaces = len(lines[0]) - len(lines[0].lstrip())
    return [line[spaces:] if len(line) > spaces else "\n" for line in lines]


if __name__ == "__main__":
    run()
