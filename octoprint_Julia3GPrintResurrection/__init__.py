# coding=utf-8
from __future__ import absolute_import

import octoprint.plugin
from octoprint.events import eventManager, Events
from flask import jsonify, make_response, request
import RPi.GPIO as GPIO

# TODO:
'''
API to change settings, and pins
API to Caliberate
API to enable/Dissable sensor, and save this information
'''


class Julia3GPrintResurrection(octoprint.plugin.StartupPlugin,
							   octoprint.plugin.EventHandlerPlugin,
							   octoprint.plugin.SettingsPlugin,
							   octoprint.plugin.TemplatePlugin,
							   octoprint.plugin.BlueprintPlugin):
	def initialize(self):
		'''
        Checks RPI.GPIO version
        Initialises board
        :return: None
        '''
		self._logger.info("Running RPi.GPIO version '{0}'".format(GPIO.VERSION))
		if GPIO.VERSION < "0.6":  # Need at least 0.6 for edge detection
			raise Exception("RPi.GPIO must be greater than 0.6")
		GPIO.setmode(GPIO.BCM)  # Use the board numbering scheme
		GPIO.setwarnings(False)  # Disable GPIO warnings

	def on_after_startup(self):
		'''
        Runs after server startup.
        initialises filaemnt sensor objects, depending on the settings from the config.yaml file
        logs the number of filament sensors active
        :return: None
        '''
		self.DET_Pin = int(self._settings.get(["DET_Pin"]))
		self.fileName = str(self._settings.get(["fileName"]))
		self.filePos = int(self._settings.get(["filePos"]))
		try:
			GPIO.setup(self.DET_Pin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
		except:
			self._logger.info("Error while initialising MKS DET Pin")

	def enableDET(self):
		GPIO.add_event_detect(self.DET_Pin, GPIO.FALLING, callback=self.saveProgress, bouncetime=300)

	def dissableDET(self):
		GPIO.remove_event_detect(self.DET_Pin)

	def get_settings_defaults(self):
		'''
        initialises default parameters
        :return:
        '''
		return dict(
			DET_Pin=19,  # MKS_DET
			fileName="None",
			filePos=0,
			tool0Target=0,
			tool1Target=0,
			bedTarget=0,
		)

	def on_event(self, event, payload):
		'''
		Enables the filament sensor(s) if a print/resume command is triggered
		Dissables the filament sensor when pause ic called.
		:param event: event to respond to
		:param payload:
		:return:
		'''
		if event in (Events.PRINT_STARTED):  # If a new print is beginning
			self.enableDET()
			self._logger.info("Enabaling DET module")
		elif event in (
				Events.PRINT_DONE, Events.PRINT_FAILED, Events.PRINT_CANCELLED, Events.ERROR):
			self.dissableDET()
			self._logger.info("Dissabling DET module")

	def get_template_configs(self):
		return [dict(type="settings", custom_bindings=False)]

	@octoprint.plugin.BlueprintPlugin.route("/saveProgress", methods=["GET"])
	def saveProgressAPI(self):
		'''
        Checks and sends the pin configuration of the filament sensor(s)
        :return: response  dict of the pin configuration
        '''
		self.saveProgress()
		# return an error or success
		return jsonify(status='progress saved')


	def saveProgress(self):
		self._printer.pause_print()
		temps =  self._printer.get_current_temperatures()
		file = self._printer.get_current_data()
		data = {"fileName": file["job"]["file"]["name"], "filePos": file["progress"]["filepos"],
				"tool0Target": temps["tool0"]["target"],
				"tool1Target": temps["tool1"]["target"],
				"bedTarget": temps["bed"]["target"]}
		print data
		octoprint.plugin.SettingsPlugin.on_settings_save(self, data)

	def get_update_information(self):
		return dict(
			Julia3GPrintResurrection=dict(
				displayName="Julia3GPrintResurrection",
				displayVersion=self._plugin_version,
				# version check: github repository
				type="github_release",
				user="FracktalWorks",
				repo="Julia3GPrintResurrection",
				current=self._plugin_version,

				# update method: pip
				pip="https://github.com/FracktalWorks/Julia3GPrintResurrection/archive/{target_version}.zip"
			)
		)

	def on_settings_save(self, data):
		octoprint.plugin.SettingsPlugin.on_settings_save(self, data)


__plugin_name__ = "Julia3GPrintResurrection"
__plugin_version__ = "0.0.1"


def __plugin_load__():
	global __plugin_implementation__
	__plugin_implementation__ = Julia3GPrintResurrection()

	global __plugin_hooks__
	__plugin_hooks__ = {
		"octoprint.plugin.softwareupdate.check_config": __plugin_implementation__.get_update_information
	}
