#!/usr/bin/env python3

import logging
import os
import threading
import time

from configparser import ConfigParser
from typing import Any, List

from simpletransformers.language_generation import LanguageGenerationModel

from db import Thing as db_Thing

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))


class ModelTextGenerator(threading.Thread):

	daemon:bool = True
	name:str = "MTGThread"

	_config:Any = None

	def __init__(self):
		threading.Thread.__init__(self)

		self._config = ConfigParser()
		self._config.read('ssi-bot.ini')

		self._model_path = os.path.join(ROOT_DIR, self._config['DEFAULT']['model_path'])

		# if you are generating on CPU, keep use_cuda and fp16 both false.
		# If you have a nvidia GPU you may enable these features
		# TODO shift these parameters into the ssi-bot.ini file
		self._model = LanguageGenerationModel("gpt2", self._model_path, use_cuda=False, args={'fp16': False})

	def run(self):

		while True:

			try:
				# get the top job in the list
				jobs = self.top_pending_jobs()
				if not jobs:
					# there are no jobs at all in the queue
					# Rest a little before attempting again
					time.sleep(30)
					continue

				for job in jobs:
					logging.info(f"Starting to generate text for job_id {job.id}.")

					# Increment the counter because we're about to generate text
					job.text_generation_attempts += 1
					job.save()

					# use the model to generate the text
					# pass a copy of the parameters to keep the job values intact
					generated_text = self.generate_text(job.text_generation_parameters.copy())
					if generated_text:
						# if the model generated text, set it into the 'job'
						job.generated_text = generated_text
						job.save()

			except:
				logging.exception("Generating text for a job failed")

	def top_pending_jobs(self)->list:
		"""
		Get a list of text that need text to be generated, by treating
		each database Thing record as a 'job'.
		Three attempts at text generation are allowed.

		"""

		query = db_Thing.select(db_Thing).\
					where(db_Thing.text_generation_parameters.is_null(False)).\
					where(db_Thing.generated_text.is_null()).\
					where(db_Thing.text_generation_attempts < 3).\
					order_by(db_Thing.created_utc)
		return list(query)

	def generate_text(self, text_generation_parameters:Any):

		start_time:Any = time.time()

		# pop the prompt out from the args
		prompt:Any = text_generation_parameters.pop('prompt')

		output_list:List[Any] = self._model.generate(prompt=prompt, args=text_generation_parameters)

		end_time:Any = time.time()
		duration:Any = round(end_time - start_time, 1)

		logging.info(f'{len(output_list)} sample(s) of text generated in {duration} seconds.')

		return output_list[0]
