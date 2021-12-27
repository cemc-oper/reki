import pandas as pd
from typing import Optional

from .grads_ctl import GradsCtl
from .grads_record_handler import GradsRecordHandler


class GradsDataHandler(object):
    """
    Parse GrADS binary data file with a ctl file.

    Get record from GrADS binary data file.
    """
    def __init__(self, a_grads_ctl: GradsCtl = None):
        if a_grads_ctl is None:
            a_grads_ctl = GradsCtl()

        self.grads_ctl = a_grads_ctl

    def get_offset_by_record_index(self, record_index: int):
        """
        get offset by record index

        Parameters
        ----------
        record_index
            record index

        Returns
        -------
        int
            record offset
        """
        if record_index >= len(self.grads_ctl.record):
            raise ValueError('record_index is too large.')

        offset = 0
        nx = self.grads_ctl.xdef['count']
        ny = self.grads_ctl.ydef['count']
        if 'sequential' in self.grads_ctl.options:
            offset += (nx * ny + 2) * 4 * record_index
        else:
            offset += nx * ny * 4 * record_index

        return offset

    def get_offset_by_index(self, var_index: int, level_index: int = 0):
        """
        get record offset by variable and level index.

        :param var_index:
        :param level_index:
        :return: record offset
        """

        record = self.get_record_by_index(var_index, level_index)
        return record.offset

    def find_record(
            self,
            name: str,
            level: int = 0,
            level_type: str = 'multi',
            valid_time: Optional[pd.Timestamp] = None,
            forecast_time: Optional[pd.Timedelta] = None,
    ):
        """
        find record index by field name, level value, level type.

        Parameters
        ----------
        name
            field name, found name in vars section of ctl files.
        level
            level value
        level_type
            multi or single
        valid_time
        forecast_time

        Returns
        -------
        GradsRecordHandler or None
        """
        cur_i = 0
        if level_type == 'single':
            a_level = 0
        elif level is not None:
            a_level = float(level)
        else:
            a_level = level

        while cur_i < len(self.grads_ctl.record):
            cur_record = self.grads_ctl.record[cur_i]
            if (
                cur_record['name'] == name
                and (level_type is None or cur_record['level_type'] == level_type)
                and (a_level is None or cur_record['level'] == a_level)
                and (valid_time is None or cur_record["valid_time"] == valid_time)
                and (forecast_time is None or cur_record["forecast_time"] == forecast_time)
            ):
                break
            cur_i += 1
        if cur_i < len(self.grads_ctl.record):
            offset = self.get_offset_by_record_index(cur_record["record_index"])
            record = GradsRecordHandler(self.grads_ctl, cur_i, offset)
            return record
        else:
            return None

    def get_record_by_index(self, var_index: int, level_index: int = 0):
        """
        get record from variable and level index.

        Parameters
        ----------
        var_index
        level_index

        Returns
        -------
        GradsRecordHandler
        """
        if var_index >= len(self.grads_ctl.vars):
            raise ValueError("variable index is too large.")

        var_levels = self.grads_ctl.vars[var_index]['levels']
        if 0 < var_levels <= level_index:
            raise ValueError("level index is too large.")

        # calculate record index
        pos = 0
        for a_var_index in range(0, var_index):
            levels = self.grads_ctl.vars[a_var_index]['levels']
            if levels == 0:
                pos += 1
            else:
                pos += levels

        pos += level_index

        offset = self.get_offset_by_record_index(pos)

        record = GradsRecordHandler(self.grads_ctl, pos, offset, var_index=var_index, level_index=level_index)
        return record
