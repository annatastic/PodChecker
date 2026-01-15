# -*- coding: utf-8 -*-

from openai import OpenAI
import whisper
import pandas as pd
import os
from perplexity import Perplexity
import ast

def process_file(podoption):
  '''
  Prepares an audio file for fact checking and calls the factcheck function with it.
  Args: podoption - an audio file
  Returns: the results of fact checking the podoption file
  '''

  model = whisper.load_model("small.en")
  transcript = model.transcribe(podoption)["text"]
  return transcript

def process_rss(rss_url):
  '''
  Retrieves the first episode from an RSS link, prepares it for fact checking, and calls the factcheck function with it.
  Args: rss_url: a link to a RSS stream for a podcast
  Returns: the results of fact checking the first episode from the rss_url
  '''

  import feedparser
  import requests

  feed = feedparser.parse(rss_url)

  if feed.bozo:
    raise RuntimeError(feed.bozo_exception)

  if not feed.entries:
      raise ValueError("RSS parsed but contains no entries")

  # grab the first episode only
  episode = feed.entries[0]

  if "enclosures" in episode and episode.enclosures:
      audio_url = episode.enclosures[0].href

      # download the file
      mp3_data = requests.get(audio_url).content

      # save it
      file_name = "episode.mp3"
      with open(file_name, "wb") as f:
          f.write(mp3_data)

      print(f"Downloaded → {file_name}")

  else:
      print("This RSS does not contain an audio enclosure.")
      return

  model = whisper.load_model("small.en")
  transcript = model.transcribe(file_name)["text"]

  return transcript

domains_df = pd.read_csv("filtered_attrs.csv")

trusted_df = domains_df[domains_df["label"] >= 5] #find domains with a reliability ranking of 5 or 6 on a scale of 1-6

def factcheck(transcript, openai_api_key, perplexity_api_key):

  #claim extraction

  system_prompt_extraction = "Please breakdown the following transcript into independent atomic facts. Ignore basic information about the podcast, " \
  "such as the name and host. Ignore promotional/ad content. Ignore personal anecdotes. Here is one example:" \
  "Input: \"She currently stars in the romantic comedy series, Love and Destiny, which premiered in 2019.\" " \
  "Output: [ {1: \"She currently stars in Love and Destiny.\"}, {2: \"Love and and Destiny is a romantic comedy series.\"}, {3 : \"Love and Destiny premiered in 2019.\"} ]"

  #initialize client with explicit OpenAI API key
  os.environ['OPENAI_API_KEY'] = openai_api_key
  client = OpenAI(
    organization='org-OJ8ihAvp3ut0vdG4Vnxzk7oR',
    project='proj_VcduimxcQxgSopyyOglx06vQ',
  )

  response = client.chat.completions.create(
    model="gpt-5-mini",
    seed=42,
    messages=[
        {"role": "system", "content": system_prompt_extraction},
        {"role": "user", "content": transcript}
    ]
  )
  generated_text = response.choices[0].message.content.strip() #our list of extracted claims
  extracted_claims = ast.literal_eval(generated_text)

  #more preprocessing

  #make container for each claim, its associated label, any supporting sources

  facts = {"num": [], "extracted_claim": [], "label": [], "sources": []}

  facts["num"] = list(range(1, len(extracted_claims) + 1))

  facts["extracted_claim"] = [list(entry.values())[0].strip() for entry in extracted_claims]

  #fact checking

  #initialize client with explicit Perplexity API key
  client = Perplexity(api_key = perplexity_api_key)

  system_prompt_fact_checking = """
  You are a fact-checker. Please check the accuracy of the provided claim, taking into account any previous claims provided as context. Return one of these ratings:
  true, false, misleading/partially true, unverifiable.
  Do not add any explanations or extraneous formatting.
  Here are 4 examples:

  Input: "Antonio Guterres is the UN Secretary General"
  Output: "true"

  Input: "Many of the Maldivians inducted into the Islamic State have come back to the Maldives"
  Output: "false"

  Input: "The Pakistani state supports or turns a blind eye to acts of terrorism"
  Output: "misleading/partially true"

  Input: "Governments can kill bitcoin by making the economic incentive to use it irrelevant"
  Output: "unverifiable"

  """

  previous_claims_context = [] # initialize an empty list for context

  #for each extracted fact:
  for claim in facts["extracted_claim"]:

    user_prompt = f"Fact to check: {claim}"
    if previous_claims_context:
      # use a sliding window of the last 5 claims to prevent context pollution from unrelated stories
      relevant_context = previous_claims_context[-5:]
      user_prompt = f"Previous claims: {relevant_context}\n\n{user_prompt}"

    while True:
      try:
        completion = client.chat.completions.create(
        model="sonar",
        messages=[
            {"role": "system", "content": system_prompt_fact_checking},
            {"role": "user", "content": user_prompt}
        ],
        web_search_options={
          "search_context_size": "medium"
        }
        )

        generated_text = completion.choices[0].message.content

        break

      except (SyntaxError, ValueError) as e: #if llm fails to format properly, call again with same fact
        print(f"Error parsing LLM output for claim '{claim}': {e}. Retrying...")
        continue

    facts["label"].append(generated_text)

    # access the URLs from the search and save as sources
    urls = [result.url for result in completion.search_results]
    annot_urls = []

    # "star" any sources that come from trusted domains
    for url in urls:
      annot_url = url
      for index, row in trusted_df.iterrows():
        if row["url"] in url:
          annot_url = "* " + annot_url
          break
      annot_urls.append(annot_url)

    facts["sources"].append(annot_urls)

    previous_claims_context.append(claim)

  df = pd.DataFrame(facts)
  pd.set_option('display.max_columns', None)
  pd.set_option('display.max_rows', None)

  return df