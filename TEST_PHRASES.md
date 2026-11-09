# RobotInsight test phrases

Say **“Hey In Site”** first, wait for its listening expression, then try one phrase at a time.

| Feature | Phrase to say | Expected behavior |
| --- | --- | --- |
| Wake word | “Hey In Site” | Robot wakes and invites you to speak. |
| Time | “What time is it?” | Gives the computer’s current local time. |
| Explicit web search | “Search for the latest NASA Artemis news.” | Shows the searching status, searches the web, and answers from the results. |
| Search without a topic | “Look on the internet.” then “NASA Artemis.” | Asks what to search for, then searches the supplied topic. |
| Indonesian search | “Cari di internet.” then “berita NASA.” | Asks for a topic in Indonesian, then searches it. |
| Cancel a search prompt | After the topic question, say “Cancel” or “Batal.” | Leaves the search prompt without querying the web. |
| Quick local explanation | “What is a transistor?” | Answers locally without a web search. |
| Explanation | “Explain why the sky looks blue.” | Gives a short local explanation. Ask for a web search to verify details. |
| Current information | “Who is the current president of the United States?” | Searches for a current answer rather than relying on model memory. |
| Camera description | “What do you see?” | Captures an image and describes what the camera can see. |
| Camera capture | “Take a picture.” | Captures an image and analyzes it. |
| Appearance question | “How do I look?” | Uses the camera to answer. |
| General conversation | “Tell me a short joke.” | Replies using the local language model without web search. |
| Spoken punctuation cleanup | “Say this sentence: Hello, world! I’m ready.” | Speaks the words without reading punctuation marks aloud. |
| Follow-up conversation | After an answer, say “Explain more,” “Why?” or “Can you explain that more simply?” | Uses the previous answer as context and gives a short follow-up without starting a new web search. |
| Return to standby | After the greeting, stay silent until the silence timeout. | Returns to waiting for the wake word without another spoken interruption. |

The web, language-model, microphone, and camera phrases require their matching service or device to be available. In particular, web-search answers also need Ollama running in the current configuration.

## New speech checks

- Say “Hey In Site” without pressing a button. The status should change from wake-word standby to listening.
- Ask a short question, then pause. Recognition should begin about 650 ms after speech stops.
- Speak a sentence longer than five seconds. It should not be cut off at the old five-second limit.
- Ask “What's the weather in Jakarta tomorrow?” for a direct weather result.
- Ask “What can you do?” to hear the supported capabilities.
- Say “Go to sleep” to end follow-up listening and return to the wake word.
- Expand the eight “Try asking” groups to see five examples in each.

The automated speech checks use synthetic audio rather than the user's voice. Real-room wake accuracy and STT accuracy still need to be checked with the user's accent and selected microphone.

## English and Indonesian switching

Say “Hey In Site,” pause for the listening expression, then try these one at a time.

- “Jam berapa sekarang?” — immediate Indonesian time reply.
- “Hari ini tanggal berapa?” — Indonesian day, month, date and time.
- “Bagaimana cuaca di Jakarta besok?” — live forecast in Indonesian.
- “Apa yang kamu lihat?” — camera description in Indonesian.
- “Cari di internet tentang berita NASA terbaru.” — real search, Indonesian summary.
- “Jelaskan pelangi dengan sederhana.” then “Beri contoh.” — Indonesian conversation and follow-up.
- “What time is it?” — switches back to English.
- “Kamu bisa apa?” — spoken feature overview.
- “Istirahat.” — returns to wake-word standby.

English uses a female Kokoro voice; Indonesian uses a separate native Piper speaker. Test in your actual room with your own accent; synthesized test audio cannot establish microphone or accent accuracy.
