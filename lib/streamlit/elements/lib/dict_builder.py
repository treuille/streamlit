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

# Python 2/3 compatibility
from __future__ import print_function, division, unicode_literals, absolute_import
from streamlit.compatibility import setup_2_3_shims

setup_2_3_shims(globals())

from copy import deepcopy

CURRENT_COLUMN_NAME = "__current_column_name__"
_CURRENT_COLUMN_NUMBER = "__current_column_number__"
_CURRENT_COLUMN_TYPE = "__current_column_type__"
INDEX_COLUMN_NAME = "__index_column_name__"

# Column name used to designate the dataframe index in JavaScript.
# Must match dataFrameProto.js
INDEX_COLUMN_DESIGNATOR = "(index)"


class DictBuilder(object):
    def __init__(self, spec, shallow=False, column=None):
        self.spec = spec
        self.is_shallow = shallow
        self.initial_column = column

    def build(self, df, spec_override=None, user_params=None, curr_col_index=0):
        """Builds a dictionary based on this object's spec plus some overrides.

        Args
        ----
        df : A dataframe. Used in order to extract things like column names.

        spec_override : A dictionary. Keys/values specified here override the
        spec used when constructing this object. May contain special tags such
        as ForEachColumn, _ParamBuilder, and _CURRENT_COLUMN_NUMBER.

        user_params : A dictionary that will be used to fetch user override
        values for the _ParamBuilder special tag.

        curr_col_index : The number of the column to use as the "current
        column", if any. If negative, then the current column is an index
        column.
        """
        if spec_override is _NoValue:
            out = {}
        else:
            out = deepcopy(spec_override)

        if self.initial_column is not None:
            curr_col_index = self.initial_column

        if curr_col_index >= len(df.columns):
            return _NoValue

        for k, spec_value in self.spec.items():
            if k in out:
                curr_out_value = out[k]
            else:
                curr_out_value = _NoValue

            value = _get_merged_spec_item(
                df, user_params, spec_value, curr_out_value, curr_col_index
            )

            if value is not _NoChange:
                out[k] = value

        return {k: v for (k, v) in out.items() if v is not _NoValue}


def _get_merged_spec_item(df, user_params, spec_value, curr_out_value, curr_col_index):

    # Handle container items and other ultra magic stuff.
    # (these need to be merged with curr_out_value, if any)

    if type(spec_value) is DictBuilder:
        return _handle_dict_builder_spec(
            df, user_params, spec_value, curr_out_value, curr_col_index
        )

    elif type(spec_value) is list:
        return _handle_list_spec(
            df, user_params, spec_value, curr_out_value, curr_col_index
        )

    # Handle simple items.
    # (for these, the value passed by the user takes precedence)

    if curr_out_value is _NoValue:
        if type(spec_value) is _ParamBuilder:
            return spec_value.build(user_params)

        elif isinstance(spec_value, ValueCycler):
            return spec_value.get(curr_col_index)

        elif isinstance(spec_value, _ColumnFinder):
            return _get_first_match(df.columns, spec_value.alternatives)

        elif spec_value == _CURRENT_COLUMN_NUMBER:
            return curr_col_index

        elif spec_value == CURRENT_COLUMN_NAME:
            return str(df.columns[curr_col_index])

        elif spec_value == _CURRENT_COLUMN_TYPE:
            return _guess_column_type(df, curr_col_index)

        elif spec_value == INDEX_COLUMN_NAME:
            return INDEX_COLUMN_DESIGNATOR

        # TODO: support '__index_column_type__'
        else:
            return spec_value
    else:
        return _NoChange


def _handle_for_each_spec(
    df, user_params, for_each_column, curr_out_value, curr_col_index
):
    spec_value = for_each_column.content_to_repeat
    return [
        _get_merged_spec_item(df, user_params, spec_value, curr_out_value, i)
        for i in range(len(df.columns))
    ]


def _handle_dict_builder_spec(
    df, user_params, spec_value, curr_out_value, curr_col_index
):
    if spec_value.is_shallow:
        if curr_out_value is _NoValue:
            return spec_value.build(
                df,
                user_params=user_params,
                spec_override=_NoValue,
                curr_col_index=curr_col_index,
            )
        else:
            return curr_out_value

    elif type(curr_out_value) is dict or curr_out_value is _NoValue:
        return spec_value.build(
            df,
            user_params=user_params,
            spec_override=curr_out_value,
            curr_col_index=curr_col_index,
        )


def _handle_list_spec(df, user_params, spec_value, curr_out_value, curr_col_index):
    parsed_spec_list = []

    for spec_item in spec_value:
        if type(spec_item) is ForEachColumn:
            items = _handle_for_each_spec(
                df, user_params, spec_item, _NoValue, curr_col_index
            )
            parsed_spec_list += items

        else:
            item = _get_merged_spec_item(
                df, user_params, spec_item, _NoValue, curr_col_index
            )
            parsed_spec_list.append(item)

    if type(curr_out_value) is list:
        return parsed_spec_list + curr_out_value

    else:
        return parsed_spec_list


class _ParamBuilder(object):
    def __init__(self, name, default_value=None):
        self.name = name
        self.default_value = default_value

    def build(self, param_override_dict):
        if self.name in param_override_dict:
            return param_override_dict[self.name]

        return self.default_value


class ForEachColumn(object):
    def __init__(self, content):
        self.content_to_repeat = content


class _ColumnFinder(object):
    def __init__(self, *alternatives):
        self.alternatives = set(alternatives)


class _NoValue(object):
    pass


class _NoChange(object):
    pass


class ValueCycler(object):
    """
    This is used within a ForEachColumn to specify values that should be cycled
    through, as we iterate through the columns.
    """

    def __init__(self, *items):
        self._items = items

    def get(self, index):
        return self._items[index % len(self._items)]


class ColorCycler(ValueCycler):
    """
    Cycles some pretty colors.
    """

    def __init__(self):
        super(ColorCycler, self).__init__(
            "#e41a1c",
            "#377eb8",
            "#4daf4a",
            "#984ea3",
            "#ff7f00",
            "#bbbb33",
            "#a65628",
            "#f781bf",
        )


def _get_first_match(available_names, wanted_names):
    for name in available_names:
        if name.lower() in wanted_names:
            return name
    raise ValueError("Data must have column with one of these names: %s" % wanted_names)


# See https://github.com/altair-viz/altair/blob/ed9eab81bba5074cdb94284d64846ba262a4ef97/altair/utils/core.py
def _guess_column_type(df, i):
    dtype = df.dtypes[i]

    if type(dtype).__name__ == "int64":
        return "ordinal"

    return "quantitative"
