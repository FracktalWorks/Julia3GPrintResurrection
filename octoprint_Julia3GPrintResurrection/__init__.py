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
		self.path = str(self._settings.get(["path"]))
		self.tool0Target = int(self._settings.get(["tool0Target"]))
		self.tool1Target = int(self._settings.get(["tool1Target"]))
		self.bedTarget = int(self._settings.get(["bedTarget"]))
		self.x = int(self._settings.get(["x"]))
		self.y = int(self._settings.get(["y"]))
		self.z = int(self._settings.get(["z"]))
		self.e = int(self._settings.get(["e"]))
		self.t = int(self._settings.get(["t"]))
		self.f = int(self._settings.get(["f"]))
		self.data = {}
		self.savingProgress = False
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
			path="None",
			filePos=0,
			tool0Target=0,
			tool1Target=0,
			bedTarget=0,
			x = 0,
			y = 0,
			z = 0,
			e = 0,
			t = 0,
			f = 0
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
		elif (event in Events.PRINT_PAUSED) and (self.savingProgress == True):
			self.data["e"] = payload["position"]["e"]
			self.data["z"] = payload["position"]["z"]
			self.data["y"] = payload["position"]["y"]
			self.data["x"] = payload["position"]["x"]
			self.data["t"] = payload["position"]["t"]
			self.data["f"] = payload["position"]["f"]
			self.on_settings_save(self.data)
			self.savingProgress = False
			self._logger.info("Print Resurrection: Print Progress saved")


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

	@octoprint.plugin.BlueprintPlugin.route("/resurrect", methods=["GET"])
	def resurrectAPI(self):
		'''
		Checks and sends the pin configuration of the filament sensor(s)
		:return: response  dict of the pin configuration
		'''
		self.resurrect()
		# return an error or success
		return jsonify(status='resurrected')

	def resurrect(self):
		if self.fileName != "None":
			self._printer.home("x", "y", "z")
			if self.bedTarget > 0:
				self._printer.set_temperature("bed", self.bedTarget)
			if self.tool0Target > 0:
				self._printer.set_temperature("tool0", self.bedTarget)
			if self.tool1Target > 0:
				self._printer.set_temperature("tool1", self.bedTarget)

			filenameToSelect = self._file_manager.path_on_disk("local", self.path)
			self._printer.select_file(path=filenameToSelect, sd=False, printAfterSelect=True, pos=self.filePos)


	def saveProgress(self):
		try:
			self._printer.pause_print()
			temps =  self._printer.get_current_temperatures()
			file = self._printer.get_current_data()
			self.data = {"fileName": file["job"]["file"]["name"], "filePos": file["progress"]["filepos"],
					"path": file["job"]["file"]["path"],
					"tool0Target": temps["tool0"]["target"],
					"tool1Target": temps["tool1"]["target"],
					"bedTarget": temps["bed"]["target"]}
			self.savingProgress = True
		except:
			self.data = {"fileName": "None", "filePos": 0,
					"path" : "None",
					"tool0Target": 0,
					"tool1Target": 0,
					"bedTarget": 0,
					"x": 0,
					"y": 0,
					"z": 0,
					"e": 0,
					"t": 0,
					"f": 0,}
			self.on_settings_save(self.data)
			self._logger.info("Could not save settings, restoring defaults")

	def on_settings_save(self, data):
		octoprint.plugin.SettingsPlugin.on_settings_save(self, data)
		self.fileName = str(self._settings.get(["fileName"]))
		self.filePos = int(self._settings.get(["filePos"]))
		self.path = str(self._settings.get(["path"]))
		self.tool0Target = int(self._settings.get(["tool0Target"]))
		self.tool1Target = int(self._settings.get(["tool1Target"]))
		self.bedTarget = int(self._settings.get(["bedTarget"]))
		self.x = int(self._settings.get(["x"]))
		self.y = int(self._settings.get(["y"]))
		self.z = int(self._settings.get(["z"]))
		self.e = int(self._settings.get(["e"]))
		self.t = int(self._settings.get(["t"]))
		self.f = int(self._settings.get(["f"]))

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

__plugin_name__ = "Julia3GPrintResurrection"
__plugin_version__ = "0.0.1"


def __plugin_load__():
	global __plugin_implementation__
	__plugin_implementation__ = Julia3GPrintResurrection()

	global __plugin_hooks__
	__plugin_hooks__ = {
		"octoprint.plugin.softwareupdate.check_config": __plugin_implementation__.get_update_information
	}
