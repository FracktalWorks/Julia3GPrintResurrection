# coding=utf-8
from __future__ import absolute_import

import octoprint.plugin
from octoprint.events import eventManager, Events
from flask import jsonify, make_response, request
import RPi.GPIO as GPIO
from octoprint.settings import settings
# TODO:
'''
Auto Resurrect
Ask about ressurection when booting
autobooting shouldnt clash with touchscreen operation
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
        Gets the settings from the config.yamal file
        :return: None
        '''
		self.DET_Pin = int(self._settings.get(["DET_Pin"]))
		self.fileName = str(self._settings.get(["fileName"]))
		self.filePos = int(self._settings.get(["filePos"]))
		self.path = str(self._settings.get(["path"]))
		self.tool0Target = float(self._settings.get(["tool0Target"]))
		#self.tool1Target = float(self._settings.get(["tool1Target"]))
		self.bedTarget = float(self._settings.get(["bedTarget"]))
		self.x = float(self._settings.get(["x"]))
		self.y = float(self._settings.get(["y"]))
		self.z = float(self._settings.get(["z"]))
		self.e = float(self._settings.get(["e"]))
		self.t = int(self._settings.get(["t"]))
		self.f = int(self._settings.get(["f"]))
		self.data = {}
		self.savingProgress = False
		try:
			GPIO.setup(self.DET_Pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
		except:
			self._logger.info("Error while initialising MKS DET Pin")

	def enableDET(self):
		"""
		Adds the interrupt detection for the MKS DET module.
		To Do: check the polarity
		:return:
		"""
		#GPIO.add_event_detect(self.DET_Pin, GPIO.FALLING, callback=self.saveProgress, bouncetime=300)
		pass

	def dissableDET(self):
		"""
		Remove interrupt detection on the MKS_DET pin
		:return:
		"""
		#GPIO.remove_event_detect(self.DET_Pin)
		pass

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
			#tool1Target=0,
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
		Callback when an event is detected. depending on the event, different things are done.
		:param event: event to respond to
		:param payload:
		:return:
		'''
		if event in (Events.PRINT_STARTED, Events.PRINT_RESUMED):  # If a new print is beginning
			self.enableDET()
			self.cleanStoredFile()
			self._logger.info("Enabaling DET module")
		elif event in (
				Events.PRINT_DONE, Events.PRINT_FAILED, Events.PRINT_CANCELLED, Events.ERROR):
			self.dissableDET()
			self._logger.info("Dissabling DET module")
		elif event in Events.PRINT_PAUSED:
			try:
				temps =  self._printer.get_current_temperatures()
				file = self._printer.get_current_data()
				self.data = {"fileName": file["job"]["file"]["name"], "filePos": file["progress"]["filepos"],
						"path": file["job"]["file"]["path"],
						"tool0Target": temps["tool0"]["target"],
						#"tool1Target": temps["tool1"]["target"],
						"bedTarget": temps["bed"]["target"]}
				self.data["e"] = payload["position"]["e"]
				self.data["z"] = payload["position"]["z"]
				self.data["y"] = payload["position"]["y"]
				self.data["x"] = payload["position"]["x"]
				self.data["t"] = payload["position"]["t"]
				self.data["f"] = payload["position"]["f"]
				self._logger.info(self.data)
				self.on_settings_save(self.data)
				self.savingProgress = False
				self._logger.info("Print Resurrection: Print Progress saved")
				self.dissableDET()
			except:
				self.data = {"fileName": "None", "filePos": 0,
							 "path": "None",
							 "tool0Target": 0,
							 #"tool1Target": 0,
							 "bedTarget": 0,
							 "x": 0,
							 "y": 0,
							 "z": 0,
							 "e": 0,
							 "t": 0,
							 "f": 0, }
				self.on_settings_save(self.data)
				self._logger.info("Could not save settings, restoring defaults")
				self.dissableDET()

	def _send_status(self, status_type, status_value, status_description=""):
		"""
		sends a plugin message, from the SockJS server
		:param status_type:
		:param status_value:
		:param status_description:
		:return:
		"""
		self._plugin_manager.send_plugin_message(self._identifier,
											 dict(type="status", status_type=status_type, status_value=status_value,
												  status_description=status_description))

	def cleanStoredFile(self):
		"""
		Clears all the stored data from the config.yaml file
		:return:
		"""
		self.data = {"fileName": "None", "filePos": 0,
					 "path": "None",
					 "tool0Target": 0,
					 #"tool1Target": 0,
					 "bedTarget": 0,
					 "x": 0,
					 "y": 0,
					 "z": 0,
					 "e": 0,
					 "t": 0,
					 "f": 0, }
		self.on_settings_save(self.data)

	def get_template_configs(self):
		'''
		Bindings for the jinja files
		:return:
		'''
		return [dict(type="settings", custom_bindings=False)]

	@octoprint.plugin.BlueprintPlugin.route("/isAvailable", methods=["GET"])
	def isAvailable(self):
		'''
		Checks if a files progress was stored
		'''
		if self.fileName != "None" and self._printer.is_ready():
			return jsonify(status='available', file = self.fileName)
		else:
			return jsonify(status='notAvailable')

	@octoprint.plugin.BlueprintPlugin.route("/saveProgress", methods=["GET"])
	def saveProgressAPI(self):
		'''
		API hook that calls the saveProgress function
        '''
		self.saveProgress()
		return jsonify(status='progress saved')

	def saveProgress(self,*args):
		'''
		Saves the progress of the file to be ressurected later
		'''

		self.savingProgress = True
		self._printer.pause_print()


	@octoprint.plugin.BlueprintPlugin.route("/resurrect", methods=["GET"])
	def resurrectAPI(self):
		'''
		API that calls resurrect function
		'''
		self.resurrect()
		# return an error or success
		return jsonify(status='resurrected')

	def resurrect(self):
		"""
		Function that actually performs the resurrection
		:return:
		"""
		if self.fileName != "None":
			if self.bedTarget > 0:
				self._printer.set_temperature("bed", self.bedTarget)
			if self.tool0Target > 0:
				self._printer.set_temperature("tool0", self.tool0Target)
			#if self.tool1Target > 0:
			#	self._printer.set_temperature("tool1", self.tool1Target)
			self._printer.home("z")
			self._printer.home(["x", "y"])
			commands = ["G90",
						"T{}".format(self.t),
						"G92 E0",
						"G1 F200 E5",
						"G1 F{}".format(self.f),
						"G92 E{}".format(self.e),
						"G1 X{} Y{}".format(self.x,self.y),
						"G1 Z{}".format(self.z)
						]
			self._printer.commands(commands)
			filenameToSelect = self._file_manager.path_on_disk("local", self.path)
			self._printer.select_file(path=filenameToSelect, sd=False, printAfterSelect=True, pos=self.filePos)
			self._send_status(status_type="PRINT_RESURRECTION_STARTED", status_value=self.fileName,
							  status_description="Print resurrection statred")

	def on_settings_save(self, data):
		"""
		Saves and updates the file settings of resurection
		:param data:
		:return:
		"""
		octoprint.plugin.SettingsPlugin.on_settings_save(self, data)
		self._settings.save()
		self.fileName = str(self._settings.get(["fileName"]))
		self.filePos = int(self._settings.get(["filePos"]))
		self.path = str(self._settings.get(["path"]))
		self.tool0Target = float(self._settings.get(["tool0Target"]))
		#self.tool1Target = float(self._settings.get(["tool1Target"]))
		self.bedTarget = float(self._settings.get(["bedTarget"]))
		self.x = float(self._settings.get(["x"]))
		self.y = float(self._settings.get(["y"]))
		self.z = float(self._settings.get(["z"]))
		self.e = float(self._settings.get(["e"]))
		self.t = float(self._settings.get(["t"]))
		self.f = float(self._settings.get(["f"]))

	def get_update_information(self):
		"""
		Function for OTA update thrpugh the software update plugin
		:return:
		"""
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
__plugin_version__ = "1.0.1"


def __plugin_load__():
	global __plugin_implementation__
	__plugin_implementation__ = Julia3GPrintResurrection()

	global __plugin_hooks__
	__plugin_hooks__ = {
		"octoprint.plugin.softwareupdate.check_config": __plugin_implementation__.get_update_information
	}

