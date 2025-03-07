#!/usr/bin/env python
#
# Electrum - lightweight Bitcoin client
# Copyright (C) 2012 thomasv@gitorious
#
# Permission is hereby granted, free of charge, to any person
# obtaining a copy of this software and associated documentation files
# (the "Software"), to deal in the Software without restriction,
# including without limitation the rights to use, copy, modify, merge,
# publish, distribute, sublicense, and/or sell copies of the Software,
# and to permit persons to whom the Software is furnished to do so,
# subject to the following conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS
# BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN
# ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
# CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import ast
from typing import Optional, TYPE_CHECKING

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (QComboBox,  QTabWidget,
                             QSpinBox,  QFileDialog, QCheckBox, QLabel,
                             QVBoxLayout, QGridLayout, QLineEdit,
                             QPushButton, QWidget, QHBoxLayout)

from electrum_dash.i18n import _, languages
from electrum_dash import util, coinchooser, paymentrequest
from electrum_dash.util import base_units_list

from electrum_dash.gui import messages

from .util import (ColorScheme, WindowModalDialog, HelpLabel, Buttons,
                   CloseButton)


if TYPE_CHECKING:
    from electrum_dash.simple_config import SimpleConfig
    from .main_window import ElectrumWindow


class SettingsDialog(WindowModalDialog):

    def __init__(self, parent: 'ElectrumWindow', config: 'SimpleConfig',
                 go_tab=None):
        WindowModalDialog.__init__(self, parent, _('Preferences'))
        self.config = config
        self.window = parent
        self.need_restart = False
        self.fx = self.window.fx
        self.wallet = self.window.wallet

        vbox = QVBoxLayout()
        tabs = QTabWidget()
        tabs.setObjectName("settings_tab")
        gui_widgets = []
        tx_widgets = []
        oa_widgets = []

        # language
        lang_help = _('Select which language is used in the GUI (after restart).')
        lang_label = HelpLabel(_('Language') + ':', lang_help)
        lang_combo = QComboBox()
        lang_combo.addItems(list(languages.values()))
        lang_keys = list(languages.keys())
        lang_cur_setting = self.config.get("language", '')
        try:
            index = lang_keys.index(lang_cur_setting)
        except ValueError:  # not in list
            index = 0
        lang_combo.setCurrentIndex(index)
        if not self.config.is_modifiable('language'):
            for w in [lang_combo, lang_label]: w.setEnabled(False)
        def on_lang(x):
            lang_request = list(languages.keys())[lang_combo.currentIndex()]
            if lang_request != self.config.get('language'):
                self.config.set_key("language", lang_request, True)
                self.need_restart = True
        lang_combo.currentIndexChanged.connect(on_lang)
        gui_widgets.append((lang_label, lang_combo))

        nz_help = _('Number of zeros displayed after the decimal point. For example, if this is set to 2, "1." will be displayed as "1.00"')
        nz_label = HelpLabel(_('Zeros after decimal point') + ':', nz_help)
        nz = QSpinBox()
        nz.setMinimum(0)
        nz.setMaximum(self.config.decimal_point)
        nz.setValue(self.config.num_zeros)
        if not self.config.is_modifiable('num_zeros'):
            for w in [nz, nz_label]: w.setEnabled(False)
        def on_nz():
            value = nz.value()
            if self.config.num_zeros != value:
                self.config.num_zeros = value
                self.config.set_key('num_zeros', value, True)
                self.window.history_list.update()
                self.window.address_list.update()
        nz.valueChanged.connect(on_nz)
        gui_widgets.append((nz_label, nz))

        msg = _('OpenAlias record, used to receive coins and to sign payment requests.') + '\n\n'\
              + _('The following alias providers are available:') + '\n'\
              + '\n'.join(['https://cryptoname.co/', 'http://xmr.link']) + '\n\n'\
              + 'For more information, see https://openalias.org'
        alias_label = HelpLabel(_('OpenAlias') + ':', msg)
        alias = self.config.get('alias','')
        self.alias_e = QLineEdit(alias)
        self.set_alias_color()
        self.alias_e.editingFinished.connect(self.on_alias_edit)
        oa_widgets.append((alias_label, self.alias_e))

        # units
        units = base_units_list
        msg = (_('Base unit of your wallet.')
               + '\n1 Dash = 1000 mDash. 1 mDash = 1000 uDash. 1 uDash = 100 duffs.\n'
               + _('This setting affects the Send tab, and all balance related fields.'))
        unit_label = HelpLabel(_('Base unit') + ':', msg)
        unit_combo = QComboBox()
        unit_combo.addItems(units)
        unit_combo.setCurrentIndex(units.index(self.window.base_unit()))
        def on_unit(x, nz):
            unit_result = units[unit_combo.currentIndex()]
            if self.window.base_unit() == unit_result:
                return
            edits = self.window.amount_e, self.window.receive_amount_e
            amounts = [edit.get_amount() for edit in edits]
            self.config.set_base_unit(unit_result)
            nz.setMaximum(self.config.decimal_point)
            self.window.update_tabs()
            for edit, amount in zip(edits, amounts):
                edit.setAmount(amount)
            self.window.update_status()
        unit_combo.currentIndexChanged.connect(lambda x: on_unit(x, nz))
        gui_widgets.append((unit_label, unit_combo))

        qr_combo = QComboBox()
        qr_combo.addItem("Default", "default")
        msg = (_("For scanning QR codes.") + "\n"
               + _("Install the zbar package to enable this."))
        qr_label = HelpLabel(_('Video Device') + ':', msg)
        from .qrreader import find_system_cameras
        system_cameras = find_system_cameras()
        for cam_desc, cam_path in system_cameras.items():
            qr_combo.addItem(cam_desc, cam_path)
        index = qr_combo.findData(self.config.get("video_device"))
        qr_combo.setCurrentIndex(index)
        on_video_device = lambda x: self.config.set_key("video_device", qr_combo.itemData(x), True)
        qr_combo.currentIndexChanged.connect(on_video_device)
        gui_widgets.append((qr_label, qr_combo))

        colortheme_combo = QComboBox()
        colortheme_combo.addItem(_('Light'), 'default')
        colortheme_combo.addItem(_('Dark'), 'dark')
        index = colortheme_combo.findData(self.config.get('qt_gui_color_theme', 'default'))
        colortheme_combo.setCurrentIndex(index)
        colortheme_label = QLabel(_('Color theme') + ':')
        def on_colortheme(x):
            self.config.set_key('qt_gui_color_theme', colortheme_combo.itemData(x), True)
            self.need_restart = True
        colortheme_combo.currentIndexChanged.connect(on_colortheme)
        gui_widgets.append((colortheme_label, colortheme_combo))

        # storage write attempts
        wr_attempts_msg = _('Value should be rised if the antivirus software'
                             ' sometimes blocks wallet write with permission'
                             ' errors.')
        wr_attempts_lb = HelpLabel(_('Wallet file write attempts') + ':',
                                         wr_attempts_msg)
        wr_attempts_sb = QSpinBox()
        wr_attempts_sb.setMinimum(1)
        wr_attempts_sb.setMaximum(30)
        wr_attempts_sb.setValue(self.window.wallet.storage.write_attempts)

        def on_wr_attempts_set_value(write_attempts):
            self.config.set_key('storage_write_attempts', write_attempts, True)
            for win in self.window.gui_object.windows:
               win.wallet.storage.write_attempts = write_attempts
        wr_attempts_sb.valueChanged.connect(on_wr_attempts_set_value)
        gui_widgets.append((wr_attempts_lb, wr_attempts_sb))

        show_dip2_cb = QCheckBox(_('Show transaction type in wallet history'))
        def_dip2 = not self.window.wallet.psman.unsupported
        show_dip2_cb.setChecked(self.config.get('show_dip2_tx_type', def_dip2))
        def on_dip2_state_changed(x):
            show_dip2 = (x == Qt.Checked)
            self.config.set_key('show_dip2_tx_type', show_dip2, True)
            self.window.history_model.refresh('on_dip2')
        show_dip2_cb.stateChanged.connect(on_dip2_state_changed)
        gui_widgets.append((show_dip2_cb, None))

        show_utxo_time_cb = QCheckBox(_('Show UTXO timestamp/islock time'))
        show_utxo_time_cb.setChecked(self.config.get('show_utxo_time', False))
        def on_show_utxo_time_changed(x):
            show_utxo_time = (x == Qt.Checked)
            self.config.set_key('show_utxo_time', show_utxo_time, True)
            self.window.utxo_list.update()
        show_utxo_time_cb.stateChanged.connect(on_show_utxo_time_changed)
        gui_widgets.append((show_utxo_time_cb, None))

        updatecheck_cb = QCheckBox(_("Automatically check for software updates"))
        updatecheck_cb.setChecked(bool(self.config.get('check_updates', False)))
        def on_set_updatecheck(v):
            self.config.set_key('check_updates', v == Qt.Checked, save=True)
        updatecheck_cb.stateChanged.connect(on_set_updatecheck)
        gui_widgets.append((updatecheck_cb, None))

        watchonly_w_cb = QCheckBox(_('Show warning for watching only wallets'))
        watchonly_w_cb.setChecked(self.config.get('watch_only_warn', True))
        def on_set_watch_only_warn(v):
            self.config.set_key('watch_only_warn', v == Qt.Checked, save=True)
        watchonly_w_cb.stateChanged.connect(on_set_watch_only_warn)
        gui_widgets.append((watchonly_w_cb, None))

        filelogging_cb = QCheckBox(_("Write logs to file"))
        filelogging_cb.setChecked(bool(self.config.get('log_to_file', False)))
        def on_set_filelogging(v):
            self.config.set_key('log_to_file', v == Qt.Checked, save=True)
            self.need_restart = True
        filelogging_cb.stateChanged.connect(on_set_filelogging)
        filelogging_cb.setToolTip(_('Debug logs can be persisted to disk. These are useful for troubleshooting.'))
        gui_widgets.append((filelogging_cb, None))

        preview_cb = QCheckBox(_('Advanced preview'))
        preview_cb.setChecked(bool(self.config.get('advanced_preview', False)))
        preview_cb.setToolTip(_("Open advanced transaction preview dialog when 'Pay' is clicked."))
        def on_preview(x):
            self.config.set_key('advanced_preview', x == Qt.Checked)
        preview_cb.stateChanged.connect(on_preview)
        tx_widgets.append((preview_cb, None))

        usechange_cb = QCheckBox(_('Use change addresses'))
        usechange_cb.setChecked(self.window.wallet.use_change)
        if not self.config.is_modifiable('use_change'): usechange_cb.setEnabled(False)
        def on_usechange(x):
            usechange_result = x == Qt.Checked
            if self.window.wallet.use_change != usechange_result:
                self.window.wallet.use_change = usechange_result
                self.window.wallet.db.put('use_change', self.window.wallet.use_change)
                multiple_cb.setEnabled(self.window.wallet.use_change)
        usechange_cb.stateChanged.connect(on_usechange)
        usechange_cb.setToolTip(_('Using change addresses makes it more difficult for other people to track your transactions.'))
        tx_widgets.append((usechange_cb, None))

        def on_multiple(x):
            multiple = x == Qt.Checked
            if self.wallet.multiple_change != multiple:
                self.wallet.multiple_change = multiple
                self.wallet.db.put('multiple_change', multiple)
        multiple_change = self.wallet.multiple_change
        multiple_cb = QCheckBox(_('Use multiple change addresses'))
        multiple_cb.setEnabled(self.wallet.use_change)
        multiple_cb.setToolTip('\n'.join([
            _('In some cases, use up to 3 change addresses in order to break '
              'up large coin amounts and obfuscate the recipient address.'),
            _('This may result in higher transactions fees.')
        ]))
        multiple_cb.setChecked(multiple_change)
        multiple_cb.stateChanged.connect(on_multiple)
        tx_widgets.append((multiple_cb, None))

        def fmt_docs(key, klass):
            lines = [ln.lstrip(" ") for ln in klass.__doc__.split("\n")]
            return '\n'.join([key, "", " ".join(lines)])

        choosers = sorted(coinchooser.COIN_CHOOSERS.keys())
        if len(choosers) > 1:
            chooser_name = coinchooser.get_name(self.config)
            msg = _('Choose coin (UTXO) selection method.  The following are available:\n\n')
            msg += '\n\n'.join(fmt_docs(*item) for item in coinchooser.COIN_CHOOSERS.items())
            chooser_label = HelpLabel(_('Coin selection') + ':', msg)
            chooser_combo = QComboBox()
            chooser_combo.addItems(choosers)
            i = choosers.index(chooser_name) if chooser_name in choosers else 0
            chooser_combo.setCurrentIndex(i)
            def on_chooser(x):
                chooser_name = choosers[chooser_combo.currentIndex()]
                self.config.set_key('coin_chooser', chooser_name)
            chooser_combo.currentIndexChanged.connect(on_chooser)
            tx_widgets.append((chooser_label, chooser_combo))

        def on_unconf(x):
            self.config.set_key('confirmed_only', bool(x))
        conf_only = bool(self.config.get('confirmed_only', False))
        unconf_cb = QCheckBox(_('Spend only confirmed coins'))
        unconf_cb.setToolTip(_('Spend only confirmed inputs.'))
        unconf_cb.setChecked(conf_only)
        unconf_cb.stateChanged.connect(on_unconf)
        tx_widgets.append((unconf_cb, None))

        def on_outrounding(x):
            self.config.set_key('coin_chooser_output_rounding', bool(x))
        enable_outrounding = bool(self.config.get('coin_chooser_output_rounding', True))
        outrounding_cb = QCheckBox(_('Enable output value rounding'))
        outrounding_cb.setToolTip(
            _('Set the value of the change output so that it has similar precision to the other outputs.') + '\n' +
            _('This might improve your privacy somewhat.') + '\n' +
            _('If enabled, at most 100 duffs might be lost due to this, per transaction.'))
        outrounding_cb.setChecked(enable_outrounding)
        outrounding_cb.stateChanged.connect(on_outrounding)
        tx_widgets.append((outrounding_cb, None))

        save_bef_send_cb = QCheckBox(_('Save local transaction before send'))
        save_bef_send = self.config.get('save_tx_before_send', False)
        save_bef_send_cb.setChecked(save_bef_send)
        def on_save_bef_send(x):
            self.config.set_key('save_tx_before_send', bool(x))
        save_bef_send_cb.stateChanged.connect(on_save_bef_send)
        tx_widgets.append((save_bef_send_cb, None))

        block_explorers = sorted(util.block_explorer_info().keys())
        BLOCK_EX_CUSTOM_ITEM = _("Custom URL")
        if BLOCK_EX_CUSTOM_ITEM in block_explorers:  # malicious translation?
            block_explorers.remove(BLOCK_EX_CUSTOM_ITEM)
        block_explorers.append(BLOCK_EX_CUSTOM_ITEM)
        msg = _('Choose which online block explorer to use for functions that open a web browser')
        block_ex_label = HelpLabel(_('Online Block Explorer') + ':', msg)
        block_ex_combo = QComboBox()
        block_ex_custom_e = QLineEdit(self.config.get('block_explorer_custom') or '')
        block_ex_combo.addItems(block_explorers)
        block_ex_combo.setCurrentIndex(
            block_ex_combo.findText(util.block_explorer(self.config) or BLOCK_EX_CUSTOM_ITEM))
        def showhide_block_ex_custom_e():
            block_ex_custom_e.setVisible(block_ex_combo.currentText() == BLOCK_EX_CUSTOM_ITEM)
        showhide_block_ex_custom_e()
        def on_be_combo(x):
            if block_ex_combo.currentText() == BLOCK_EX_CUSTOM_ITEM:
                on_be_edit()
            else:
                be_result = block_explorers[block_ex_combo.currentIndex()]
                self.config.set_key('block_explorer_custom', None, False)
                self.config.set_key('block_explorer', be_result, True)
            showhide_block_ex_custom_e()
        block_ex_combo.currentIndexChanged.connect(on_be_combo)
        def on_be_edit():
            val = block_ex_custom_e.text()
            try:
                val = ast.literal_eval(val)  # to also accept tuples
            except:
                pass
            self.config.set_key('block_explorer_custom', val)
        block_ex_custom_e.editingFinished.connect(on_be_edit)
        block_ex_hbox = QHBoxLayout()
        block_ex_hbox.setContentsMargins(0, 0, 0, 0)
        block_ex_hbox.setSpacing(0)
        block_ex_hbox.addWidget(block_ex_combo)
        block_ex_hbox.addWidget(block_ex_custom_e)
        block_ex_hbox_w = QWidget()
        block_ex_hbox_w.setLayout(block_ex_hbox)
        tx_widgets.append((block_ex_label, block_ex_hbox_w))

        # Fiat Currency
        hist_checkbox = QCheckBox()
        hist_capgains_checkbox = QCheckBox()
        fiat_address_checkbox = QCheckBox()
        ccy_combo = QComboBox()
        ex_combo = QComboBox()

        def update_currencies():
            if not self.window.fx: return
            currencies = sorted(self.fx.get_currencies(self.fx.get_history_config()))
            ccy_combo.clear()
            ccy_combo.addItems([_('None')] + currencies)
            if self.fx.is_enabled():
                ccy_combo.setCurrentIndex(ccy_combo.findText(self.fx.get_currency()))

        def update_history_cb():
            if not self.fx: return
            hist_checkbox.setChecked(self.fx.get_history_config())
            hist_checkbox.setEnabled(self.fx.is_enabled())

        def update_fiat_address_cb():
            if not self.fx: return
            fiat_address_checkbox.setChecked(self.fx.get_fiat_address_config())

        def update_history_capgains_cb():
            if not self.fx: return
            hist_capgains_checkbox.setChecked(self.fx.get_history_capital_gains_config())
            hist_capgains_checkbox.setEnabled(hist_checkbox.isChecked())

        def update_exchanges():
            if not self.fx: return
            b = self.fx.is_enabled()
            ex_combo.setEnabled(b)
            if b:
                h = self.fx.get_history_config()
                c = self.fx.get_currency()
                exchanges = self.fx.get_exchanges_by_ccy(c, h)
            else:
                exchanges = self.fx.get_exchanges_by_ccy('USD', False)
            ex_combo.blockSignals(True)
            ex_combo.clear()
            ex_combo.addItems(sorted(exchanges))
            ex_combo.setCurrentIndex(ex_combo.findText(self.fx.config_exchange()))
            ex_combo.blockSignals(False)

        def on_currency(hh):
            if not self.fx: return
            b = bool(ccy_combo.currentIndex())
            ccy = str(ccy_combo.currentText()) if b else None
            self.fx.set_enabled(b)
            if b and ccy != self.fx.ccy:
                self.fx.set_currency(ccy)
            update_history_cb()
            update_exchanges()
            self.window.update_fiat()

        def on_exchange(idx):
            exchange = str(ex_combo.currentText())
            if self.fx and self.fx.is_enabled() and exchange and exchange != self.fx.exchange.name():
                self.fx.set_exchange(exchange)

        def on_history(checked):
            if not self.fx: return
            self.fx.set_history_config(checked)
            update_exchanges()
            self.window.history_model.refresh('on_history')
            if self.fx.is_enabled() and checked:
                self.fx.trigger_update()
            update_history_capgains_cb()

        def on_history_capgains(checked):
            if not self.fx: return
            self.fx.set_history_capital_gains_config(checked)
            self.window.history_model.refresh('on_history_capgains')

        def on_fiat_address(checked):
            if not self.fx: return
            self.fx.set_fiat_address_config(checked)
            self.window.address_list.refresh_headers()
            self.window.address_list.update()

        update_currencies()
        update_history_cb()
        update_history_capgains_cb()
        update_fiat_address_cb()
        update_exchanges()
        ccy_combo.currentIndexChanged.connect(on_currency)
        hist_checkbox.stateChanged.connect(on_history)
        hist_capgains_checkbox.stateChanged.connect(on_history_capgains)
        fiat_address_checkbox.stateChanged.connect(on_fiat_address)
        ex_combo.currentIndexChanged.connect(on_exchange)

        fiat_widgets = []
        fiat_widgets.append((QLabel(_('Fiat currency')), ccy_combo))
        fiat_widgets.append((QLabel(_('Source')), ex_combo))
        fiat_widgets.append((QLabel(_('Show history rates')), hist_checkbox))
        fiat_widgets.append((QLabel(_('Show capital gains in history')), hist_capgains_checkbox))
        fiat_widgets.append((QLabel(_('Show Fiat balance for addresses')), fiat_address_checkbox))

        tabs_info = [
            (gui_widgets, _('General')),
            (tx_widgets, _('Transactions')),
            (fiat_widgets, _('Fiat')),
            (oa_widgets, _('OpenAlias')),
        ]
        for widgets, name in tabs_info:
            tab = QWidget()
            tab.setObjectName(name)
            tab_vbox = QVBoxLayout(tab)
            grid = QGridLayout()
            for a,b in widgets:
                i = grid.rowCount()
                if b:
                    if a:
                        grid.addWidget(a, i, 0)
                    grid.addWidget(b, i, 1)
                else:
                    grid.addWidget(a, i, 0, 1, 2)
            tab_vbox.addLayout(grid)
            tab_vbox.addStretch(1)
            tabs.addTab(tab, name)

        vbox.addWidget(tabs)
        vbox.addStretch(1)
        vbox.addLayout(Buttons(CloseButton(self)))
        self.setLayout(vbox)

        if go_tab is not None:
            go_tab_w = tabs.findChild(QWidget, go_tab)
            if go_tab_w:
                tabs.setCurrentWidget(go_tab_w)

    def set_alias_color(self):
        if not self.config.get('alias'):
            self.alias_e.setStyleSheet("")
            return
        if self.window.alias_info:
            alias_addr, alias_name, validated = self.window.alias_info
            self.alias_e.setStyleSheet((ColorScheme.GREEN if validated else ColorScheme.RED).as_stylesheet(True))
        else:
            self.alias_e.setStyleSheet(ColorScheme.RED.as_stylesheet(True))

    def on_alias_edit(self):
        self.alias_e.setStyleSheet("")
        alias = str(self.alias_e.text())
        self.config.set_key('alias', alias, True)
        if alias:
            self.window.fetch_alias()
