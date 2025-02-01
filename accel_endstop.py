# Motors synchronization script
#
# Copyright (C) 2025  Maksim Bolgov <maksim8024@gmail.com>
#
# This file may be distributed under the terms of the GNU GPLv3 license.
from . import adxl345

REG_THRESH_TAP = 0x1D
REG_DUR = 0x21
REG_INT_MAP = 0x2F
REG_TAP_AXES = 0x2A
REG_INT_ENABLE = 0x2E
REG_INT_SOURCE = 0x30
DUR_SCALE = 0.000625  # 0.625 msec / LSB
TAP_SCALE = 0.0625 * adxl345.FREEFALL_ACCEL  # 62.5mg/LSB * Earth gravity in mm/s**2
ADXL345_REST_TIME = .1

class AccelEndstop:
    def __init__(self, config):
        self.printer = config.get_printer()
        self.gcode = self.printer.lookup_object('gcode')
        gcode_macro = self.printer.load_object(config, 'gcode_macro')
        self.activate_gcode = gcode_macro.load_template(
            config, 'activate_gcode', '')
        self.deactivate_gcode = gcode_macro.load_template(
            config, 'deactivate_gcode', '')
        self.chip_name = config.get('accel_chip')
        if self.chip_name.split()[0] not in 'adxl345':
            raise config.error(f'accel_endstop: Not supported '
                               f'chip: {self.chip_name}')
        int_type = config.get('int_type')
        if int_type not in ['int1', 'int2']:
            raise config.error('int_pin must specify one '
                               'of int1 or int2 pins')
        self.int_map = 0x40 if int_type == 'int2' else 0x0
        # Register virtual_endstop pin
        self.int_pin = config.get('int_pin')
        ppins = self.printer.lookup_object('pins')
        pin_params = ppins.parse_pin(self.int_pin, True, True)
        self.int_inv = pin_params['invert']
        ppins.register_chip(self.chip_name, self)
        pin_desc = f"{self.chip_name}:virtual_endstop"
        ppins.allow_multi_use_pin(pin_desc)
        self.mcu_endstop = ppins.setup_pin('endstop', self.int_pin)
        # Read config
        self.tap_thresh = config.getfloat(
            'tap_thresh', 5000., minval=TAP_SCALE, maxval=16000.)
        self.tap_dur = config.getfloat(
            'tap_dur', 0.01, above=DUR_SCALE, maxval=0.159)
        # Register commands and callbacks
        self.gcode.register_command('SET_ACCEL_ENDSTOP',
                                    self.cmd_SET_ACCEL_ENDSTOP,
                                    desc=self.cmd_SET_ACCEL_ENDSTOP_help)
        self.printer.register_event_handler('klippy:connect',
                                            self.handle_connect)
        self.printer.register_event_handler("homing:homing_move_begin",
                                            self.handle_homing_move_begin)
        self.printer.register_event_handler("homing:homing_move_end",
                                            self.handle_homing_move_end)

    def setup_tap_regs(self):
        self.chip.set_reg(REG_THRESH_TAP, int(self.tap_thresh / TAP_SCALE))
        self.chip.set_reg(REG_DUR, int(self.tap_dur / DUR_SCALE))

    def handle_connect(self):
        self.toolhead = self.printer.lookup_object('toolhead')
        self.chip = self.printer.lookup_object(self.chip_name)
        self.chip.set_reg(adxl345.REG_POWER_CTL, 0x00)
        self.chip.set_reg(adxl345.REG_DATA_FORMAT, 0x0B)
        if self.int_inv:
            self.chip.set_reg(adxl345.REG_DATA_FORMAT, 0x2B)
        self.chip.set_reg(REG_INT_MAP, self.int_map)
        self.chip.set_reg(REG_TAP_AXES, 0x7)
        self.setup_tap_regs()

    def setup_pin(self, pin_type, pin_params):
        cn = self.chip_name
        ppins = self.printer.lookup_object('pins')
        if pin_type != 'endstop' or pin_params['pin'] != 'virtual_endstop':
            raise ppins.error(f"{cn} virtual endstop only useful as endstop")
        if pin_params['invert'] or pin_params['pullup']:
            raise ppins.error(f"Can not pullup/invert {cn} virtual pin")
        return self.mcu_endstop

    def _try_clear_tap(self):
        tries = 8
        while tries > 0:
            val = self.chip.read_reg(REG_INT_SOURCE)
            if not (val & 0x40):
                return
            tries -= 1
        raise self.gcode.error(
            "ADXL345 tap triggered before move,"
            " it may be set too sensitive")

    def handle_homing_move_begin(self, hmove):
        if self.mcu_endstop not in hmove.get_mcu_endstops():
            return
        self.activate_gcode.run_gcode_from_command()
        self.toolhead.flush_step_generation()
        self.toolhead.dwell(ADXL345_REST_TIME)
        print_time = self.toolhead.get_last_move_time()
        clock = self.chip.mcu.print_time_to_clock(print_time)
        self.chip.set_reg(REG_INT_ENABLE, 0x00, clock)
        self.chip.read_reg(REG_INT_SOURCE)
        self.chip.set_reg(REG_INT_ENABLE, 0x40, clock)
        self.chip.set_reg(adxl345.REG_POWER_CTL, 0x08, clock)
        self._try_clear_tap()

    def handle_homing_move_end(self, hmove):
        if self.mcu_endstop not in hmove.get_mcu_endstops():
            return
        self.toolhead.dwell(ADXL345_REST_TIME)
        print_time = self.toolhead.get_last_move_time()
        clock = self.chip.mcu.print_time_to_clock(print_time)
        self.chip.set_reg(REG_INT_ENABLE, 0x00, clock)
        self.chip.set_reg(adxl345.REG_POWER_CTL, 0x00)
        self.deactivate_gcode.run_gcode_from_command()
        self._try_clear_tap()

    cmd_SET_ACCEL_ENDSTOP_help = 'Set TAP_THRESH or TAP_DUR for accel endstop'
    def cmd_SET_ACCEL_ENDSTOP(self, gcmd):
        if (gcmd.get('TAP_THRESH', None) is None
             and gcmd.get('TAP_DUR', None) is None):
            gcmd.respond_info(f'TAP_THRESH={self.tap_thresh},'
                              f' TAP_DUR={self.tap_dur}')
        self.tap_thresh = gcmd.get_float('TAP_THRESH', self.tap_thresh,
                                         minval=TAP_SCALE, maxval=16000.)
        self.tap_dur = gcmd.get_float('TAP_DUR', self.tap_dur,
                                      above=DUR_SCALE, maxval=0.159)
        self.setup_tap_regs()


def load_config(config):
    return AccelEndstop(config)
