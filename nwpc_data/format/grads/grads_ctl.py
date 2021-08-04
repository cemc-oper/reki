import sys
import datetime
import re
from pathlib import Path
import logging
from typing import Optional, Union


logger = logging.getLogger(__name__)


class GradsCtl(object):
    def __init__(self):
        self.dset = ''
        self.title = ''
        self.options = list()
        self.data_endian = 'little'
        self.local_endian = sys.byteorder
        self.yrev = 0
        self.undef = None

        self.start_time = None
        self.forecast_time = None

        self.record = []


class GradsCtlParser(object):
    def __init__(self, grads_ctl: Optional[GradsCtl] = None):
        self.ctl_file_path = None

        if grads_ctl is None:
            grads_ctl = GradsCtl()
        self.grads_ctl = grads_ctl

        self.ctl_file_lines = list()
        self.cur_no = -1

        self.parser_mapper = {
            'ctl_file_name': self._parse_ctl_file_name,
            'dset': self._parse_dset,
            'options': self._parse_options,
            'title': self._parse_title,
            'undef': self._parse_undef,
            'xdef': self._parse_dimension,
            'ydef': self._parse_dimension,
            'zdef': self._parse_dimension,
            'tdef': self._parse_tdef,
            'vars': self._parse_vars,
        }

    def set_ctl_file_path(self, ctl_file_path: Union[Path, str]):
        self.ctl_file_path = Path(ctl_file_path)
        with open(ctl_file_path) as f:
            lines = f.readlines()
            self.ctl_file_lines = [l.strip() for l in lines]
            self.cur_no = 0

    def parse(self, ctl_file_path: Union[Path, str]):
        self.set_ctl_file_path(ctl_file_path)
        total_lines = len(self.ctl_file_lines)
        while self.cur_no < total_lines:
            cur_line = self.ctl_file_lines[self.cur_no]
            first_word = cur_line[0:cur_line.find(' ')]
            if first_word.lower() in self.parser_mapper:
                self.parser_mapper[first_word]()
            self.cur_no += 1

        self._parse_ctl_file_name()

        return self.grads_ctl

    def _parse_ctl_file_name(self):
        ctl_file_name = Path(self.ctl_file_path).name

        if (
                self.grads_ctl.start_time is None
                and self.grads_ctl.forecast_time is None
        ):
            logger.debug("guess start time and forecast time")

            if ctl_file_name.startswith("post.ctl_"):
                # check for grapes meso v4.0 which format is:
                #   post.ctl_201408111202900
                if re.match(r"post.ctl_[0-9]{15}", ctl_file_name):
                    self.grads_ctl.start_time = datetime.datetime.strptime(ctl_file_name[9:19], "%Y%m%d%H")
                    self.grads_ctl.forecast_time = datetime.timedelta(hours=int(ctl_file_name[19:22]))
                # check for grapes gfs which format is
                #   post.ctl_2014081112_001
                elif re.match(r"post.ctl_[0-9]{10}_[0-9]{3}", ctl_file_name):
                    self.grads_ctl.start_time = datetime.datetime.strptime(ctl_file_name[9:19], "%Y%m%d%H")
                    self.grads_ctl.forecast_time = datetime.timedelta(hours=int(ctl_file_name[21:24]))
                else:
                    logger.warning("We can't recognize ctl file name. ")

    def _parse_dset(self):
        cur_line = self.ctl_file_lines[self.cur_no]
        dset = cur_line[4:].strip()
        if dset[0] == '^':
            file_dir = Path(self.ctl_file_path).parent
            dset = Path(file_dir, dset[1:])

        self.grads_ctl.dset = dset

    def _parse_options(self):
        cur_line = self.ctl_file_lines[self.cur_no]
        options = cur_line[7:].strip().split(' ')
        self.grads_ctl.options.extend(options)
        for an_option in options:
            if an_option == 'big_endian':
                self.grads_ctl.data_endian = 'big'
            elif an_option == 'little_endian':
                self.grads_ctl.data_endian = 'little'
            elif an_option == 'yrev':
                self.grads_ctl.yrev = True

    def _parse_title(self):
        cur_line = self.ctl_file_lines[self.cur_no]
        title = cur_line[5:].strip()
        self.grads_ctl.title = title

    def _parse_undef(self):
        cur_line = self.ctl_file_lines[self.cur_no]
        undef = cur_line[5:].strip()
        self.grads_ctl.undef = float(undef)

    def _parse_dimension(self):
        """
        parser for keywords xdef, ydef and zdef
        """
        cur_line = self.ctl_file_lines[self.cur_no].lower()
        tokens = cur_line.split()
        dim_name = tokens[0]  # xdef, ydef, zdef
        dimension_type = tokens[2]

        dimension_parser_map = {
            'linear': self._parse_linear_dimension,
            'levels': self._parse_levels_dimension
        }

        if dimension_type in dimension_parser_map:
            dimension_parser_map[dimension_type](dim_name, tokens)
        else:
            raise NotImplemented('dimension_type is not supported: {dimension_type}'.format(
                dimension_type=dimension_type
            ))

    def _parse_linear_dimension(self, dim_name, tokens):
        # x use linear mapping
        if len(tokens) < 4:
            raise Exception("%s parser error" % dim_name)
        count = int(tokens[1])
        start = float(tokens[3])
        step = float(tokens[4])
        levels = [start + step * n for n in range(count)]
        setattr(self.grads_ctl, dim_name, {
            'type': 'linear',
            'count': count,
            'start': start,
            'step': step,
            'values': levels
        })

    def _parse_levels_dimension(self, dim_name, tokens):
        levels = list()
        count = int(tokens[1])
        if len(tokens) > 2:
            levels = [float(l) for l in tokens[3:]]
        i = len(levels)
        while i < count:
            self.cur_no += 1
            cur_line = self.ctl_file_lines[self.cur_no]
            levels.append(float(cur_line))
            i += 1

        setattr(self.grads_ctl, dim_name, {
            'type': 'levels',
            'count': count,
            'values': levels
        })

    def _parse_tdef(self):
        cur_line = self.ctl_file_lines[self.cur_no]
        parts = cur_line.strip().split()
        assert parts[2] == "linear"
        assert len(parts) == 5

        count = int(parts[1])
        start_string = parts[3]
        increment_string = parts[4]

        start_date = GradsCtlParser._parse_start_time(start_string)
        time_step = GradsCtlParser._parse_increment_time(increment_string)

        values = [start_date + time_step * i for i in range(count)]

        self.grads_ctl.tdef = {
            'type': 'linear',
            'count': count,
            'start': start_date,
            'step': time_step,
            'values': values
        }

    @classmethod
    def _parse_start_time(cls, start_string):
        # parse start time
        # format:
        #     hh:mmZddmmmyyyy
        # where:
        #     hh	=	hour (two digit integer)
        #     mm	=	minute (two digit integer)
        #     dd	=	day (one or two digit integer)
        #     mmm	=	3-character month
        #     yyyy	=	year (may be a two or four digit integer;
        #                       2 digits implies a year between 1950 and 2049)
        start_date = datetime.datetime.now()
        if start_string[3] == ':':
            raise NotImplemented('Not supported time with hh')
        elif len(start_string) == 12:
            start_date = datetime.datetime.strptime(start_string.lower(), '%Hz%d%b%Y')
        else:
            raise NotImplemented('start time not supported: {start_string}'.format(start_string=start_string))
        return start_date

    @classmethod
    def _parse_increment_time(cls, increment_string):
        # parse increment time
        # format:
        #     vvkk
        # where:
        #     vv	=	an integer number, 1 or 2 digits
        #     kk	=	mn (minute)
        #             hr (hour)
        #             dy (day)
        #             mo (month)
        #             yr (year)
        vv = int(increment_string[:-2])
        kk = increment_string[-2:]

        kk_map = {
            'mn': (lambda v: datetime.timedelta(minutes=v)),
            'hr': (lambda v: datetime.timedelta(hours=v)),
            'dy': (lambda v: datetime.timedelta(days=v))
        }
        if kk in kk_map:
            return kk_map[kk](vv)
        else:
            raise NotImplemented('{kk} is not supported'.format(kk=kk))

    def _parse_vars(self):
        self._parse_variables()
        self._parse_records()

    def _parse_variables(self):
        var_list = list()

        parts = self.ctl_file_lines[self.cur_no].strip().split()
        assert len(parts) == 2
        count = int(parts[1])
        for _ in range(count):
            # parse one var line
            self.cur_no += 1
            cur_line = self.ctl_file_lines[self.cur_no].strip()
            parts = cur_line.split()
            # we currently use old style of var record.
            # TODO: check for new type of record from GrADS v2.0.2

            var_name = parts[0]
            levels = int(parts[1])
            units = parts[2]
            description = " ".join(parts[3:])

            cur_var = {
                'name': var_name,
                'levels': levels,
                'units': units,
                'description': description
            }
            var_list.append(cur_var)

        self.grads_ctl.vars = var_list

    def _parse_records(self):
        record_list = list()
        record_index = 0
        for a_var_record in self.grads_ctl.vars:
            if a_var_record['levels'] == 0:
                record_list.append({
                    'name': a_var_record['name'],
                    'level_type': 'single',
                    'level': 0,
                    'level_index': 0,
                    'units': a_var_record['units'],
                    'description': a_var_record['description'],
                    'record_index': record_index
                })
                record_index += 1
            else:
                for level_index in range(0, a_var_record["levels"]):
                    a_level = self.grads_ctl.zdef["values"][level_index]
                    record_list.append({
                        'name': a_var_record['name'],
                        'level_type': 'multi',
                        'level': a_level,
                        'level_index': level_index,
                        'units': a_var_record['units'],
                        'description': a_var_record['description'],
                        'record_index': record_index
                    })
                    record_index += 1

        self.grads_ctl.record = record_list
