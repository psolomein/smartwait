# Import the database object (db) from the main application module
# We will define this inside /app/__init__.py in the next sections.
from app import speech,time,io

# Google API
def google_stt(speech_file,
                    file_length=58,
                    sr=48000,
                    enc=speech.RecognitionConfig.AudioEncoding.OGG_OPUS):
    '''Function to call Google Speech-to-Text API'''
    
    tic = time.perf_counter() # Get timing
    client = speech.SpeechClient()
    audio = speech.RecognitionAudio(uri=speech_file)
    
    # Config Google StT API
    config = speech.RecognitionConfig(
        encoding=enc,
        sample_rate_hertz=sr,
        language_code="ru-RU",
        enable_word_time_offsets=True,
        enable_automatic_punctuation=True)

    print('Using short-running recognize.')
    
    with io.open(speech_file, "rb") as audio_file:
        content = audio_file.read()
    audio = speech.RecognitionAudio(content=content)
    operation = client.recognize(config=config, audio=audio)
    response = operation
    
    t=[] # Transcripts
    w=[] #Words
    t_start =[] # Word time start
    t_end = [] # Word time end
    
    # Printing out the output:
    for i,result in enumerate(response.results):
        t.append(result.alternatives[0].transcript)
        alternative = result.alternatives[0]
        for word_info in alternative.words:
            w.append(word_info.word)
            t_start.append(word_info.start_time)
            t_end.append(word_info.end_time)
    t=' '.join(t)
    toc = time.perf_counter()
    comm = io.StringIO()
    print(f"Transcribed in {toc - tic:0.4f} seconds",file=comm)
    return t,comm.getvalue()