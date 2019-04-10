#!/usr/bin/env python
# -*- coding: utf-8 -*-
# #########################################################################
# Copyright (c) 2018, UChicago Argonne, LLC. All rights reserved.         #
#                                                                         #
# Copyright 2018. UChicago Argonne, LLC. This software was produced       #
# under U.S. Government contract DE-AC02-06CH11357 for Argonne National   #
# Laboratory (ANL), which is operated by UChicago Argonne, LLC for the    #
# U.S. Department of Energy. The U.S. Government has rights to use,       #
# reproduce, and distribute this software.  NEITHER THE GOVERNMENT NOR    #
# UChicago Argonne, LLC MAKES ANY WARRANTY, EXPRESS OR IMPLIED, OR        #
# ASSUMES ANY LIABILITY FOR THE USE OF THIS SOFTWARE.  If software is     #
# modified to produce derivative works, such modified software should     #
# be clearly marked, so as not to confuse it with the version available   #
# from ANL.                                                               #
#                                                                         #
# Additionally, redistribution and use in source and binary forms, with   #
# or without modification, are permitted provided that the following      #
# conditions are met:                                                     #
#                                                                         #
#     * Redistributions of source code must retain the above copyright    #
#       notice, this list of conditions and the following disclaimer.     #
#                                                                         #
#     * Redistributions in binary form must reproduce the above copyright #
#       notice, this list of conditions and the following disclaimer in   #
#       the documentation and/or other materials provided with the        #
#       distribution.                                                     #
#                                                                         #
#     * Neither the name of UChicago Argonne, LLC, Argonne National       #
#       Laboratory, ANL, the U.S. Government, nor the names of its        #
#       contributors may be used to endorse or promote products derived   #
#       from this software without specific prior written permission.     #
#                                                                         #
# THIS SOFTWARE IS PROVIDED BY UChicago Argonne, LLC AND CONTRIBUTORS     #
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT       #
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS       #
# FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL UChicago     #
# Argonne, LLC OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT,        #
# INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING,    #
# BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;        #
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER        #
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT      #
# LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN       #
# ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE         #
# POSSIBILITY OF SUCH DAMAGE.                                             #
# #########################################################################

import sys, numpy

import scipy.constants as codata
m2ev = codata.c * codata.h / codata.e

from PyQt5.QtGui import QPalette, QFont, QColor
from PyQt5.QtWidgets import QApplication, QMessageBox

from orangewidget.widget import OWAction
from orangewidget import gui
from orangewidget.settings import Setting

from oasys.widgets import widget
from oasys.widgets import gui as oasysgui
from oasys.widgets.gui import ConfirmDialog
from oasys.widgets import congruence

from oasys.util.oasys_util import TriggerIn, TriggerOut
from oasys.widgets.exchange import DataExchangeObject

from syned.storage_ring.light_source import LightSource
from syned.widget.widget_decorator import WidgetDecorator

class EnergyBinning(object):
    def __init__(self,
                 energy_value_from = 0.0,
                 energy_value_to   = 0.0,
                 energy_step       = 0.0,
                 power_step        = None):
        self.energy_value_from       = energy_value_from
        self.energy_value_to         = energy_value_to
        self.energy_step             = energy_step
        self.power_step              = power_step

    def __str__(self):
        return str(self.energy_value_from) + ", " + str(self.energy_value_to) + ", " + str(self.energy_step) + ", " + str(self.power_step)

class PowerLoopPoint(widget.OWWidget):

    name = "Power Density Loop Point"
    description = "Tools: LoopPoint"
    icon = "icons/cycle.png"
    maintainer = "Luca Rebuffi"
    maintainer_email = "lrebuffi(@at@)anl.gov"
    priority = 5
    category = "User Defined"
    keywords = ["data", "file", "load", "read"]

    inputs = WidgetDecorator.syned_input_data()
    inputs.append(("Trigger", TriggerIn, "passTrigger"))
    inputs.append(("ExchangeData", DataExchangeObject, "acceptExchangeData" ))

    outputs = [{"name":"Trigger",
                "type":TriggerOut,
                "doc":"Trigger",
                "id":"Trigger"}]
    want_main_area = 1

    current_new_object = 0
    number_of_new_objects = 0
    
    total_current_new_object = 0
    total_new_objects = Setting(0)

    run_loop = True
    suspend_loop = False

    energies = Setting("")

    seed_increment=Setting(1)

    autobinning = Setting(1)

    auto_n_step = Setting(1001)
    auto_perc_total_power = Setting(99)

    refine_around_harmonic = Setting(1)
    percentage_of_points_around_harmonic = Setting(50)
    flux_factor = Setting(2.0)
    number_of_points_last = Setting(3)

    electron_energy = Setting(6.0)
    K_vertical = Setting(1.943722)
    K_horizontal = Setting(0.0)
    period_length = Setting(0.025)
    number_of_periods = Setting(184)
    theta_x=Setting(0.0)
    theta_z=Setting(0.0)

    current_energy_binning = 0
    current_energy_value = None
    current_energy_value_central = None
    current_energy_value_half_power = None
    current_energy_step = None
    current_power_step = None

    energy_binnings = None

    test_mode = False

    external_binning = False

    #################################
    process_last = True
    #################################

    def __init__(self):
        self.runaction = OWAction("Start", self)
        self.runaction.triggered.connect(self.startLoop)
        self.addAction(self.runaction)

        self.runaction = OWAction("Stop", self)
        self.runaction.triggered.connect(self.stopLoop)
        self.addAction(self.runaction)

        self.runaction = OWAction("Suspend", self)
        self.runaction.triggered.connect(self.suspendLoop)
        self.addAction(self.runaction)

        self.runaction = OWAction("Restart", self)
        self.runaction.triggered.connect(self.restartLoop)
        self.addAction(self.runaction)

        self.setFixedWidth(1200)
        self.setFixedHeight(710)

        button_box = oasysgui.widgetBox(self.controlArea, "", addSpace=True, orientation="horizontal")

        self.start_button = gui.button(button_box, self, "Start", callback=self.startLoop)
        self.start_button.setFixedHeight(35)

        stop_button = gui.button(button_box, self, "Stop", callback=self.stopLoop)
        stop_button.setFixedHeight(35)
        font = QFont(stop_button.font())
        font.setBold(True)
        stop_button.setFont(font)
        palette = QPalette(stop_button.palette()) # make a copy of the palette
        palette.setColor(QPalette.ButtonText, QColor('red'))
        stop_button.setPalette(palette) # assign new palette

        self.stop_button = stop_button

        button_box = oasysgui.widgetBox(self.controlArea, "", addSpace=True, orientation="horizontal")

        suspend_button = gui.button(button_box, self, "Suspend", callback=self.suspendLoop)
        suspend_button.setFixedHeight(35)
        font = QFont(suspend_button.font())
        font.setBold(True)
        suspend_button.setFont(font)
        palette = QPalette(suspend_button.palette()) # make a copy of the palette
        palette.setColor(QPalette.ButtonText, QColor('orange'))
        suspend_button.setPalette(palette) # assign new palette

        self.re_start_button = gui.button(button_box, self, "Restart", callback=self.restartLoop)
        self.re_start_button.setFixedHeight(35)
        self.re_start_button.setEnabled(False)

        tabs = oasysgui.tabWidget(self.controlArea)
        tab_loop = oasysgui.createTabPage(tabs, "Loop Management")
        tab_und = oasysgui.createTabPage(tabs, "Undulator")

        left_box_2 = oasysgui.widgetBox(tab_und, "Parameters From Syned", addSpace=False, orientation="vertical", width=385, height=560)

        oasysgui.lineEdit(left_box_2, self, "electron_energy", "Ring Energy [GeV]", labelWidth=260, valueType=float, orientation="horizontal").setReadOnly(True)
        oasysgui.lineEdit(left_box_2, self, "number_of_periods", "Number of Periods", labelWidth=260,  valueType=float, orientation="horizontal").setReadOnly(True)
        oasysgui.lineEdit(left_box_2, self, "period_length", "Undulator Period [m]", labelWidth=260,  valueType=float, orientation="horizontal").setReadOnly(True)
        oasysgui.lineEdit(left_box_2, self, "K_vertical", "K Vertical", labelWidth=260,  valueType=float, orientation="horizontal").setReadOnly(True)
        oasysgui.lineEdit(left_box_2, self, "K_horizontal", "K Horizontal", labelWidth=260,  valueType=float, orientation="horizontal").setReadOnly(True)

        left_box_1 = oasysgui.widgetBox(tab_loop, "", addSpace=False, orientation="vertical", width=385, height=560)

        oasysgui.lineEdit(left_box_1, self, "seed_increment", "Source Montecarlo Seed Increment", labelWidth=250, valueType=int, orientation="horizontal")

        gui.separator(left_box_1)

        gui.comboBox(left_box_1, self, "autobinning", label="Energy Binning",
                                            items=["Manual", "Automatic"], labelWidth=150,
                                            callback=self.set_Autobinning, sendSelectedValue=False, orientation="horizontal")

        self.autobinning_box_1 = oasysgui.widgetBox(left_box_1, "", addSpace=False, orientation="vertical", height=220)
        self.autobinning_box_2 = oasysgui.widgetBox(left_box_1, "", addSpace=False, orientation="vertical", height=20)

        oasysgui.lineEdit(self.autobinning_box_1, self, "auto_n_step", "Number of Steps", labelWidth=250, valueType=int, orientation="horizontal")
        oasysgui.lineEdit(self.autobinning_box_1, self, "auto_perc_total_power", "% Total Power", labelWidth=250, valueType=float, orientation="horizontal")

        gui.comboBox(self.autobinning_box_1, self, "refine_around_harmonic", label="Increment Points around Harmonic",
                                            items=["No", "Yes (Odd Only)", "Yes (All)"], labelWidth=250,
                                            callback=self.set_RefineAroundHarmonic, sendSelectedValue=False, orientation="horizontal")

        self.autobinning_box_1_1 = oasysgui.widgetBox(self.autobinning_box_1, "", addSpace=False, orientation="vertical", height=75)
        self.autobinning_box_1_2 = oasysgui.widgetBox(self.autobinning_box_1, "", addSpace=False, orientation="vertical", height=75)

        oasysgui.lineEdit(self.autobinning_box_1_1, self, "percentage_of_points_around_harmonic", "% of Points Around Harmonics", labelWidth=250, valueType=float, orientation="horizontal")
        oasysgui.lineEdit(self.autobinning_box_1_1, self, "flux_factor", "Energy Range by \u00b1 Harmonic Flux Factor", labelWidth=250, valueType=float, orientation="horizontal")
        oasysgui.lineEdit(self.autobinning_box_1_1, self, "number_of_points_last", "Number Of Points After last Harmonic", labelWidth=250, valueType=int, orientation="horizontal")

        gui.button(self.autobinning_box_1, self, "Reload Spectrum", callback=self.read_spectrum_file)

        oasysgui.widgetLabel(self.autobinning_box_1, "Energy From, Energy To, Energy Step [eV], Power [W]")

        oasysgui.widgetLabel(self.autobinning_box_2, "Energy From, Energy To, Energy Step [eV]")

        def write_text():
            self.energies = self.text_area.toPlainText()

        self.text_area = oasysgui.textArea(height=125, width=385, readOnly=False)
        self.text_area.setText(self.energies)
        self.text_area.setStyleSheet("background-color: white; font-family: Courier, monospace;")
        self.text_area.textChanged.connect(write_text)

        left_box_1.layout().addWidget(self.text_area)

        gui.separator(left_box_1)

        self.le_number_of_new_objects = oasysgui.lineEdit(left_box_1, self, "total_new_objects", "Total Energy Values", labelWidth=250, valueType=int, orientation="horizontal")
        self.le_number_of_new_objects.setReadOnly(True)
        font = QFont(self.le_number_of_new_objects.font())
        font.setBold(True)
        self.le_number_of_new_objects.setFont(font)
        palette = QPalette(self.le_number_of_new_objects.palette()) # make a copy of the palette
        palette.setColor(QPalette.Text, QColor('dark blue'))
        palette.setColor(QPalette.Base, QColor(243, 240, 160))
        self.le_number_of_new_objects.setPalette(palette)

        self.le_number_of_new_objects = oasysgui.lineEdit(left_box_1, self, "number_of_new_objects", "Current Binning Energy Values", labelWidth=250, valueType=int, orientation="horizontal")
        self.le_number_of_new_objects.setReadOnly(True)
        font = QFont(self.le_number_of_new_objects.font())
        font.setBold(True)
        self.le_number_of_new_objects.setFont(font)
        palette = QPalette(self.le_number_of_new_objects.palette()) # make a copy of the palette
        palette.setColor(QPalette.Text, QColor('dark blue'))
        palette.setColor(QPalette.Base, QColor(243, 240, 160))
        self.le_number_of_new_objects.setPalette(palette)

        gui.separator(left_box_1)

        le_current_value = oasysgui.lineEdit(left_box_1, self, "total_current_new_object", "Total New " + self.get_object_name(), labelWidth=250, valueType=int, orientation="horizontal")
        le_current_value.setReadOnly(True)
        font = QFont(le_current_value.font())
        font.setBold(True)
        le_current_value.setFont(font)
        palette = QPalette(le_current_value.palette()) # make a copy of the palette
        palette.setColor(QPalette.Text, QColor('dark blue'))
        palette.setColor(QPalette.Base, QColor(243, 240, 160))
        le_current_value.setPalette(palette)

        le_current_value = oasysgui.lineEdit(left_box_1, self, "current_new_object", "Current Binning New " + self.get_object_name(), labelWidth=250, valueType=int, orientation="horizontal")
        le_current_value.setReadOnly(True)
        font = QFont(le_current_value.font())
        font.setBold(True)
        le_current_value.setFont(font)
        palette = QPalette(le_current_value.palette()) # make a copy of the palette
        palette.setColor(QPalette.Text, QColor('dark blue'))
        palette.setColor(QPalette.Base, QColor(243, 240, 160))
        le_current_value.setPalette(palette)

        le_current_value = oasysgui.lineEdit(left_box_1, self, "current_energy_value", "Current Energy Value", labelWidth=250, valueType=float, orientation="horizontal")
        le_current_value.setReadOnly(True)
        font = QFont(le_current_value.font())
        font.setBold(True)
        le_current_value.setFont(font)
        palette = QPalette(le_current_value.palette()) # make a copy of the palette
        palette.setColor(QPalette.Text, QColor('dark blue'))
        palette.setColor(QPalette.Base, QColor(243, 240, 160))
        le_current_value.setPalette(palette)

        gui.rubber(self.controlArea)

        tabs = oasysgui.tabWidget(self.mainArea)
        tabs.setFixedHeight(self.height()-15)
        tabs.setFixedWidth(685)

        tab_plot = oasysgui.createTabPage(tabs, "Cumulated Power")
        tab_flux = oasysgui.createTabPage(tabs, "Spectral Flux")

        self.cumulated_power_plot = oasysgui.plotWindow(tab_plot)
        self.cumulated_power_plot.setFixedHeight(self.height()-20)
        self.cumulated_power_plot.setFixedWidth(680)
        self.cumulated_power_plot.setGraphXLabel("Energy [eV]")
        self.cumulated_power_plot.setGraphYLabel("Cumulated Power [W]")
        self.cumulated_power_plot.setGraphTitle("Cumulated Power")

        self.spectral_flux_plot = oasysgui.plotWindow(tab_flux)
        self.spectral_flux_plot.setFixedHeight(self.height()-20)
        self.spectral_flux_plot.setFixedWidth(680)
        self.spectral_flux_plot.setGraphXLabel("Energy [eV]")
        self.spectral_flux_plot.setGraphYLabel("Flux [ph/s/.1%bw]")
        self.spectral_flux_plot.setGraphTitle("Spectral Flux")

        self.set_Autobinning()

    def set_Autobinning(self):
        self.autobinning_box_1.setVisible(self.autobinning==1)
        self.autobinning_box_2.setVisible(self.autobinning==0)
        self.text_area.setReadOnly(self.autobinning==1)
        self.text_area.setFixedHeight(125 if self.autobinning==1 else 320)
        self.cumulated_power_plot.clear()
        self.cumulated_power_plot.setEnabled(self.autobinning==1)
        self.spectral_flux_plot.clear()
        self.spectral_flux_plot.setEnabled(self.autobinning==1)

        self.set_RefineAroundHarmonic()

    def set_RefineAroundHarmonic(self):
        self.autobinning_box_1_1.setVisible(self.refine_around_harmonic>=1)
        self.autobinning_box_1_2.setVisible(self.refine_around_harmonic==0)

    def read_spectrum_file(self):
        try:
            data = numpy.loadtxt("autobinning.dat", skiprows=1)

            calculated_data = DataExchangeObject(program_name="ShadowOui", widget_name="PowerLoopPoint")
            calculated_data.add_content("spectrum_data", data)

            self.acceptExchangeData(calculated_data)
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e), QMessageBox.Ok)

            if self.IS_DEVELOP: raise e

    def receive_syned_data(self, data):
        if not data is None:
            try:
                if not data._light_source is None and isinstance(data._light_source, LightSource):
                    light_source = data._light_source

                    self.electron_energy = light_source._electron_beam._energy_in_GeV

                    self.K_horizontal = light_source._magnetic_structure._K_horizontal
                    self.K_vertical = light_source._magnetic_structure._K_vertical
                    self.period_length = light_source._magnetic_structure._period_length
                    self.number_of_periods = light_source._magnetic_structure._number_of_periods
                else:
                    raise ValueError("Syned data not correct")
            except Exception as exception:
                QMessageBox.critical(self, "Error", str(exception), QMessageBox.Ok)

                if self.IS_DEVELOP: raise exception

    def receive_specific_syned_data(self, data):
        raise NotImplementedError()

    def acceptExchangeData(self, exchange_data):
        if not exchange_data is None:
            try:
                write_file = True

                try:
                    data = exchange_data.get_content("spectrum_data")
                    write_file = False
                except:
                    try:
                        data = exchange_data.get_content("srw_data")
                    except:
                        data = exchange_data.get_content("xoppy_data")

                energies                     = data[:, 0]
                flux_through_finite_aperture = data[:, 1]

                if self.refine_around_harmonic >= 1:
                    if not (0.0 < self.percentage_of_points_around_harmonic < 100.0): raise Exception("% of Points Around Harmonics should be  > 0.0 and < 100.0")
                    if not (1.0 < self.flux_factor <= 2.0): raise Exception("% of Points Around Harmonics should be > 1.0 and <= 2.0")
                    congruence.checkStrictlyPositiveNumber(self.number_of_points_last, "Number Of Points After last Harmonic")

                    minimum_energy_of_spectrum = energies[0]
                    maximum_energy_of_spectrum = energies[-1]

                    first_harmonic_energy = self.__get_resonance_energy()
                    red_shifted_energy = self.__get_red_shifted_energy(energies, flux_through_finite_aperture, first_harmonic_energy)

                    harmonics = []
                    red_shifted_energies = []

                    current_harmonic_nr = 1
                    current_harmonic_energy = first_harmonic_energy
                    current_red_shifted_energy = red_shifted_energy

                    while True:
                        if current_harmonic_energy > minimum_energy_of_spectrum: harmonics.append(current_harmonic_energy)
                        if current_red_shifted_energy > minimum_energy_of_spectrum: red_shifted_energies.append(current_red_shifted_energy)
                        else: red_shifted_energies.append(minimum_energy_of_spectrum) # to manage incomplete patterns as well/

                        current_harmonic_nr += 2 if self.refine_around_harmonic == 1 else 1
                        current_harmonic_energy = first_harmonic_energy * current_harmonic_nr
                        if current_harmonic_energy >= maximum_energy_of_spectrum: break
                        current_red_shifted_energy = self.__get_red_shifted_energy(energies, flux_through_finite_aperture, current_harmonic_energy)

                if write_file:
                    file = open("autobinning.dat", "w")
                    file.write("Energy Flux")

                    for energy, flux in zip(energies, flux_through_finite_aperture):
                        file.write("\n" + str(energy) + " " + str(flux))

                    file.flush()
                    file.close()

                if self.autobinning==0:
                    if write_file: QMessageBox.information(self, "Info", "File autobinning.dat written on working directory, switch to Automatic binning to load it", QMessageBox.Ok)
                else:
                    if write_file: QMessageBox.information(self, "Info", "File autobinning.dat written on working directory", QMessageBox.Ok)

                    congruence.checkStrictlyPositiveNumber(self.auto_n_step, "(Auto) % Number of Steps")
                    congruence.checkStrictlyPositiveNumber(self.auto_perc_total_power, "(Auto) % Total Power")

                    energy_step = energies[1]-energies[0]

                    power_down = flux_through_finite_aperture * (1e3 * energy_step * codata.e)
                    power_up = numpy.append(power_down[1:], [power_down[-1]])

                    cumulated_power = numpy.cumsum((power_down + power_up)/2)

                    total_power = cumulated_power[-1]

                    self.cumulated_power_plot.clear()
                    self.cumulated_power_plot.addCurve(energies, cumulated_power, replace=True, legend="Cumulated Power")
                    self.cumulated_power_plot.setGraphXLabel("Energy [eV]")
                    self.cumulated_power_plot.setGraphYLabel("Cumulated Power [W]")
                    self.cumulated_power_plot.setGraphTitle("Total Power: " + str(round(total_power, 2)) + " W")

                    self.spectral_flux_plot.clear()
                    self.spectral_flux_plot.addCurve(energies, flux_through_finite_aperture, replace=True, legend="Spectral Flux")
                    self.spectral_flux_plot.setGraphXLabel("Energy [eV]")
                    self.spectral_flux_plot.setGraphYLabel("Flux [ph/s/.1%bw]")
                    self.spectral_flux_plot.setGraphTitle("Spectral Flux")

                    good = numpy.where(cumulated_power <= self.auto_perc_total_power*0.01*total_power)

                    energies        = energies[good]
                    cumulated_power = cumulated_power[good]

                    if self.refine_around_harmonic == 0:
                        interpolated_cumulated_power = numpy.linspace(start=0, stop=numpy.max(cumulated_power), num=self.auto_n_step)
                    else:
                        total_n_points_harmonics = int(self.auto_n_step*self.percentage_of_points_around_harmonic*0.01)

                        number_of_points_around_harmonic = int(total_n_points_harmonics/len(harmonics))
                        n_points_out_harmonic = int((self.auto_n_step - total_n_points_harmonics)/len(harmonics))

                        if n_points_out_harmonic <= 1:
                            self.auto_n_step = len(harmonics) + total_n_points_harmonics

                        previous_after_harmonic = minimum_energy_of_spectrum

                        interpolated_cumulated_power = numpy.array([])

                        for red_shifted, harmonic in zip(red_shifted_energies, harmonics):
                            delta_e = harmonic-red_shifted

                            before = numpy.where(numpy.logical_and(previous_after_harmonic <= energies, energies < red_shifted))
                            after = numpy.where(numpy.logical_and(red_shifted <= energies, energies < harmonic + delta_e))

                            cumulated_power_before = cumulated_power[before]
                            cumulated_power_after = cumulated_power[after]

                            interpolated_cumulated_power = numpy.append(interpolated_cumulated_power,
                                                        numpy.linspace(start=cumulated_power_before[0], stop=cumulated_power_before[-1], num=n_points_out_harmonic))
                            interpolated_cumulated_power = numpy.append(interpolated_cumulated_power,
                                                        numpy.linspace(start=cumulated_power_after[0], stop=cumulated_power_after[-1], num=number_of_points_around_harmonic))

                            previous_after_harmonic = harmonic + delta_e

                        last = numpy.where(numpy.logical_and(previous_after_harmonic <= energies, energies <= maximum_energy_of_spectrum))

                        cumulated_power_last = cumulated_power[last]

                        interpolated_cumulated_power = numpy.append(interpolated_cumulated_power,
                                                       numpy.linspace(start=cumulated_power_last[0], stop=cumulated_power_last[-1], num=self.number_of_points_last))

                    interpolated_lower_energies = numpy.interp(interpolated_cumulated_power, cumulated_power, energies)
                    interpolated_upper_energies = numpy.append(interpolated_lower_energies, [energies[-1] + energy_step])
                    energy_bins                 = numpy.diff(interpolated_upper_energies)

                    interpolated_cumulated_power = interpolated_cumulated_power[:-1]
                    interpolated_lower_energies = interpolated_lower_energies[:-1]
                    interpolated_upper_energies = interpolated_upper_energies[1:-1]

                    if self.refine_around_harmonic == 0:
                        power_steps = numpy.ones(len(energy_bins))*(interpolated_cumulated_power[1]-interpolated_cumulated_power[0])
                    else:
                        power_steps = numpy.ediff1d(numpy.append(numpy.zeros(1), interpolated_cumulated_power))

                    flux_steps = numpy.interp(interpolated_lower_energies, energies, flux_through_finite_aperture)

                    self.energy_binnings = []
                    self.total_new_objects = 0

                    self.cumulated_power_plot.addCurve(interpolated_lower_energies, interpolated_cumulated_power, replace=False, legend="Energy Binning",
                                                       color="red", linestyle=" ", symbol="+")

                    self.spectral_flux_plot.addCurve(interpolated_lower_energies, flux_steps, replace=False, legend="Energy Binning",
                                                       color="red", linestyle=" ", symbol="+")

                    text = ""

                    for energy_from, energy_to, energy_bin, power_step in zip(interpolated_lower_energies,
                                                                              interpolated_upper_energies,
                                                                              energy_bins,
                                                                              power_steps
                                                                              ):
                        energy_binning = EnergyBinning(energy_value_from=round(energy_from, 3),
                                                       energy_value_to=round(energy_to, 3),
                                                       energy_step=round(energy_bin, 3),
                                                       power_step=round(power_step, 4))

                        text += str(round(energy_from, 3)) + ", " + \
                                str(round(energy_to, 3))   + ", " + \
                                str(round(energy_bin, 3))  + ", " + \
                                str(round(power_step, 4)) + "\n"

                        self.energy_binnings.append(energy_binning)
                        self.total_new_objects += 1

                    self.text_area.setText(text)

                    self.external_binning = True
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e), QMessageBox.Ok)

                if self.IS_DEVELOP: raise e
        else:
            self.energy_binnings = None
            self.total_new_objects = 0
            self.external_binning = False
            self.text_area.setText("")

    def calculate_energy_binnings(self):
        if not self.external_binning:
            self.total_new_objects = 0

            rows = self.energies.split("\n")
            for row in rows:
                data = row.split(",")
                if len(data) == 3:
                    if self.energy_binnings is None: self.energy_binnings = []

                    energy_binning = EnergyBinning(energy_value_from=float(data[0].strip()),
                                                   energy_value_to=float(data[1].strip()),
                                                   energy_step=float(data[2].strip()))
                    self.energy_binnings.append(energy_binning)
                    self.total_new_objects += int((energy_binning.energy_value_to - energy_binning.energy_value_from) / energy_binning.energy_step)

    def calculate_number_of_new_objects(self):
        if len(self.energy_binnings) > 0:
            if self.external_binning:
                self.number_of_new_objects = 1
            else:
                energy_binning = self.energy_binnings[self.current_energy_binning]

                self.number_of_new_objects = int((energy_binning.energy_value_to - energy_binning.energy_value_from) / energy_binning.energy_step)
        else:
            self.number_of_new_objects = 0

    def reset_values(self):
        self.current_new_object = 0
        self.total_current_new_object = 0
        self.current_energy_value = None
        self.current_energy_value_central = None
        self.current_energy_value_half_power = None
        self.current_energy_step = None
        self.current_energy_binning = 0
        self.current_power_step = None

        if not self.external_binning: self.energy_binnings = None

    def startLoop(self):
        try:
            self.calculate_energy_binnings()

            self.current_new_object = 1
            self.total_current_new_object = 1
            self.current_energy_binning = 0
            self.current_energy_value             = round(self.energy_binnings[0].energy_value_from, 8)
            self.current_energy_step              = round(self.energy_binnings[0].energy_step, 8)
            self.current_power_step               = None if self.energy_binnings[0].power_step is None else round(self.energy_binnings[0].power_step, 8)
            self.calculate_number_of_new_objects()

            self.start_button.setEnabled(False)
            self.text_area.setEnabled(False)
            self.setStatusMessage("Running " + self.get_object_name() + " " + str(self.total_current_new_object) + " of " + str(self.total_new_objects))
            self.send("Trigger", TriggerOut(new_object=True,
                                            additional_parameters={"energy_value"   : self.current_energy_value,
                                                                   "energy_step"    : self.current_energy_step,
                                                                   "power_step"     : -1 if self.current_power_step is None else self.current_power_step,
                                                                   "seed_increment" : self.seed_increment,
                                                                   "test_mode"      : False}))
        except Exception as e:
            if self.IS_DEVELOP : raise e
            else: pass

    def stopLoop(self):
        try:
            if ConfirmDialog.confirmed(parent=self, message="Confirm Interruption of the Loop?"):
                self.run_loop = False
                self.reset_values()
                self.setStatusMessage("Interrupted by user")
        except Exception as e:
            if self.IS_DEVELOP : raise e
            else: pass

    def suspendLoop(self):
        try:
            if ConfirmDialog.confirmed(parent=self, message="Confirm Suspension of the Loop?"):
                self.run_loop = False
                self.suspend_loop = True
                self.stop_button.setEnabled(False)
                self.re_start_button.setEnabled(True)
                self.setStatusMessage("Suspended by user")
        except Exception as e:
            if self.IS_DEVELOP : raise e
            else: pass


    def restartLoop(self):
        try:
            self.run_loop = True
            self.suspend_loop = False
            self.stop_button.setEnabled(True)
            self.re_start_button.setEnabled(False)
            self.passTrigger(TriggerIn(new_object=True))
        except Exception as e:
            if self.IS_DEVELOP : raise e
            else: pass

    def get_object_name(self):
        return "Beam"

    def passTrigger(self, trigger):
        if self.run_loop:
            if trigger:
                if trigger.interrupt:
                    self.reset_values()
                    self.start_button.setEnabled(True)
                    self.text_area.setEnabled(True)
                    self.setStatusMessage("")
                    self.send("Trigger", TriggerOut(new_object=False))
                elif trigger.new_object:
                    if self.energy_binnings is None: self.calculate_energy_binnings()

                    if self.current_energy_binning < len(self.energy_binnings):
                        energy_binning = self.energy_binnings[self.current_energy_binning]

                        self.total_current_new_object += 1

                        if self.current_new_object < self.number_of_new_objects:
                            if self.current_energy_value is None:
                                self.current_new_object = 1
                                self.calculate_number_of_new_objects()
                                self.current_energy_value = round(energy_binning.energy_value_from, 8)
                            else:
                                self.current_new_object += 1
                                self.current_energy_value = round(self.current_energy_value + energy_binning.energy_step, 8)

                            self.current_power_step = None if energy_binning.power_step is None else round(energy_binning.power_step, 8)

                            self.setStatusMessage("Running " + self.get_object_name() + " " + str(self.total_current_new_object) + " of " + str(self.total_new_objects))
                            self.start_button.setEnabled(False)
                            self.text_area.setEnabled(False)
                            self.send("Trigger", TriggerOut(new_object=True,
                                                            additional_parameters={"energy_value"   : self.current_energy_value,
                                                                                   "energy_step"    : energy_binning.energy_step,
                                                                                   "power_step"     : -1 if self.current_power_step is None else self.current_power_step,
                                                                                   "seed_increment" : self.seed_increment,
                                                                                   "test_mode"      : False}))
                        else:
                            self.current_energy_binning += 1

                            if self.current_energy_binning < len(self.energy_binnings):
                                energy_binning = self.energy_binnings[self.current_energy_binning]

                                self.current_new_object = 1
                                self.calculate_number_of_new_objects()
                                self.current_energy_value = round(energy_binning.energy_value_from, 8)
                                self.current_power_step = None if energy_binning.power_step is None else round(energy_binning.power_step, 8)

                                self.setStatusMessage("Running " + self.get_object_name() + " " + str(self.total_current_new_object) + " of " + str(self.total_new_objects))
                                self.start_button.setEnabled(False)
                                self.text_area.setEnabled(False)
                                self.send("Trigger", TriggerOut(new_object=True,
                                                                additional_parameters={"energy_value"   : self.current_energy_value,
                                                                                       "energy_step"    : energy_binning.energy_step,
                                                                                       "power_step"     : -1 if self.current_power_step is None else self.current_power_step,
                                                                                       "seed_increment" : self.seed_increment,
                                                                                       "test_mode"      : False}))
                            else:
                                self.reset_values()
                                self.start_button.setEnabled(True)
                                self.text_area.setEnabled(True)
                                self.setStatusMessage("")
                                self.send("Trigger", TriggerOut(new_object=False))
                    else:
                        self.reset_values()
                        self.start_button.setEnabled(True)
                        self.text_area.setEnabled(True)
                        self.setStatusMessage("")
                        self.send("Trigger", TriggerOut(new_object=False))
        else:
            if not self.suspend_loop:
                self.reset_values()
                self.start_button.setEnabled(True)
                self.text_area.setEnabled(True)

            self.send("Trigger", TriggerOut(new_object=False))
            self.setStatusMessage("")
            self.suspend_loop = False
            self.run_loop = True


    def __get_resonance_energy(self, harmonic_number=1):
        gamma = 1e9*self.electron_energy / (codata.m_e *  codata.c**2 / codata.e)

        resonance_wavelength = (self.period_length / (2.0*gamma**2)) * (1 + self.K_vertical**2 / 2.0 + self.K_horizontal**2 / 2.0 + gamma**2 * (self.theta_x**2 + self.theta_z ** 2))

        return harmonic_number*m2ev/resonance_wavelength

    def __get_red_shifted_energy(self, energies, flux_through_finite_aperture, harmonic_energy):
        harmonic_index = (numpy.abs(energies - harmonic_energy)).argmin()
        harmonic_flux = flux_through_finite_aperture[harmonic_index]

        current_index = harmonic_index
        current_difference = harmonic_flux
        previous_difference = 1.1*harmonic_flux

        while(previous_difference > current_difference):
            current_index -= 1
            previous_difference = current_difference
            current_difference = numpy.abs(self.flux_factor*harmonic_flux-flux_through_finite_aperture[current_index])

        red_shifted_index = current_index

        min_flux = numpy.min(flux_through_finite_aperture[max(red_shifted_index, 0):harmonic_index])
        max_flux = numpy.max(flux_through_finite_aperture[max(red_shifted_index, 0):harmonic_index])

        red_shifted_energy = energies[red_shifted_index]

        if min_flux < self.flux_factor*harmonic_flux < max_flux:
            xp = flux_through_finite_aperture[max(red_shifted_index, 0):harmonic_index][::-1]
            yp = energies[max(red_shifted_index, 0): harmonic_index][::-1]

            try:
                if numpy.all(xp[:, 1:] >= xp[:, :-1], axis=1): # monotonic
                    red_shifted_energy = numpy.interp(self.flux_factor*harmonic_flux, xp, yp)
            except:
                pass

        return red_shifted_energy

if __name__ == "__main__":
    a = QApplication(sys.argv)
    ow = PowerLoopPoint()
    ow.show()
    a.exec_()
    ow.saveSettings()

