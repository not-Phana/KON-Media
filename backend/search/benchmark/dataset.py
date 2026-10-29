"""Benchmark dataset containing Tuning and Held-out evaluation queries with verified ground truth."""

from typing import List, Dict, Any
from backend.search.models import CandidateResult

TUNING_QUERIES: List[Dict[str, Any]] = [
    # 1. Exact Titles & Artists
    {
        "query_id": "tune_exact_01",
        "query": "Queen Bohemian Rhapsody",
        "category": "exact",
        "expected_relevant_ids": ["cand_queen_studio", "cand_queen_lyrics"],
        "relevance_grades": {
            "cand_queen_studio": 3,
            "cand_queen_lyrics": 2,
            "cand_queen_live": 1,
            "cand_queen_muppets": 0,
            "cand_queen_trailer": 0,
        },
        "expected_artist": "Queen",
        "expected_title": "Bohemian Rhapsody",
        "ideal_duration": 355.0,
        "candidate_pool": [
            CandidateResult(id="cand_queen_trailer", title="Bohemian Rhapsody | Official Trailer [HD] | 20th Century FOX", uploader="20th Century Studios", duration=140.0, platform="youtube", views=25000000),
            CandidateResult(id="cand_queen_muppets", title="The Muppets: Bohemian Rhapsody", uploader="The Muppets", duration=288.0, platform="youtube", views=95000000),
            CandidateResult(id="cand_queen_live", title="Queen - Bohemian Rhapsody (Live Aid 1985)", uploader="Queen Official", duration=385.0, platform="youtube", views=120000000),
            CandidateResult(id="cand_queen_lyrics", title="Queen - Bohemian Rhapsody (Lyrics)", uploader="QueenLyrics", duration=355.0, platform="youtube", views=45000000),
            CandidateResult(id="cand_queen_studio", title="Queen - Bohemian Rhapsody (Official Video Remastered)", uploader="Queen Official", duration=359.0, platform="youtube", views=1600000000),
        ],
    },
    {
        "query_id": "tune_exact_02",
        "query": "The Weeknd Blinding Lights",
        "category": "exact",
        "expected_relevant_ids": ["cand_weeknd_audio", "cand_weeknd_video"],
        "relevance_grades": {
            "cand_weeknd_audio": 3,
            "cand_weeknd_video": 3,
            "cand_weeknd_live": 1,
            "cand_weeknd_cover": 0,
            "cand_weeknd_remix": 1,
        },
        "expected_artist": "The Weeknd",
        "expected_title": "Blinding Lights",
        "ideal_duration": 200.0,
        "candidate_pool": [
            CandidateResult(id="cand_weeknd_cover", title="Blinding Lights - The Weeknd (Acoustic Guitar Cover)", uploader="AcousticSessions", duration=195.0, platform="youtube"),
            CandidateResult(id="cand_weeknd_remix", title="The Weeknd - Blinding Lights (Major Lazer Remix)", uploader="The Weeknd", duration=198.0, platform="youtube"),
            CandidateResult(id="cand_weeknd_live", title="The Weeknd - Blinding Lights (Live at the Super Bowl)", uploader="NFL", duration=240.0, platform="youtube"),
            CandidateResult(id="cand_weeknd_audio", title="The Weeknd - Blinding Lights (Official Audio)", uploader="TheWeekndVEVO", duration=202.0, platform="youtube"),
            CandidateResult(id="cand_weeknd_video", title="The Weeknd - Blinding Lights (Official Music Video)", uploader="TheWeekndVEVO", duration=263.0, platform="youtube"),
        ],
    },
    {
        "query_id": "tune_exact_03",
        "query": "Daft Punk Get Lucky",
        "category": "exact",
        "expected_relevant_ids": ["cand_daft_official", "cand_daft_audio"],
        "relevance_grades": {
            "cand_daft_official": 3,
            "cand_daft_audio": 3,
            "cand_daft_cover": 0,
            "cand_daft_parody": 0,
        },
        "expected_artist": "Daft Punk",
        "expected_title": "Get Lucky",
        "ideal_duration": 248.0,
        "candidate_pool": [
            CandidateResult(id="cand_daft_parody", title="Daft Punk - Get Lucky Minecraft Parody", uploader="BlockTunes", duration=230.0, platform="youtube"),
            CandidateResult(id="cand_daft_cover", title="Get Lucky - Daft Punk (Smooth Jazz Cover)", uploader="JazzVibes", duration=310.0, platform="youtube"),
            CandidateResult(id="cand_daft_audio", title="Daft Punk - Get Lucky (Full Audio Track)", uploader="DaftPunkVEVO", duration=248.0, platform="youtube"),
            CandidateResult(id="cand_daft_official", title="Daft Punk - Get Lucky (Official Audio) ft. Pharrell Williams, Nile Rodgers", uploader="Daft Punk", duration=248.0, platform="youtube"),
        ],
    },

    # 2. Incomplete Titles & Typos
    {
        "query_id": "tune_typo_01",
        "query": "bohemain rhapsdy quen",
        "category": "incomplete_typos",
        "expected_relevant_ids": ["cand_queen_studio", "cand_queen_lyrics"],
        "relevance_grades": {
            "cand_queen_studio": 3,
            "cand_queen_lyrics": 2,
            "cand_queen_live": 1,
            "cand_unrelated_rap": 0,
        },
        "expected_artist": "Queen",
        "expected_title": "Bohemian Rhapsody",
        "candidate_pool": [
            CandidateResult(id="cand_unrelated_rap", title="Rhap City - Freestyle Hip Hop Mix 2024", uploader="RapBeats", duration=180.0, platform="youtube"),
            CandidateResult(id="cand_queen_live", title="Queen - Bohemian Rhapsody (Live at Wembley)", uploader="Queen Official", duration=360.0, platform="youtube"),
            CandidateResult(id="cand_queen_lyrics", title="Queen - Bohemian Rhapsody (Lyrics)", uploader="QueenLyrics", duration=355.0, platform="youtube"),
            CandidateResult(id="cand_queen_studio", title="Queen - Bohemian Rhapsody (Official Video)", uploader="Queen Official", duration=359.0, platform="youtube"),
        ],
    },
    {
        "query_id": "tune_typo_02",
        "query": "blindin lites the weeknd",
        "category": "incomplete_typos",
        "expected_relevant_ids": ["cand_weeknd_audio", "cand_weeknd_video"],
        "relevance_grades": {
            "cand_weeknd_audio": 3,
            "cand_weeknd_video": 3,
            "cand_unrelated_lights": 0,
        },
        "expected_artist": "The Weeknd",
        "expected_title": "Blinding Lights",
        "candidate_pool": [
            CandidateResult(id="cand_unrelated_lights", title="Traffic Lights Explained - Road Rules", uploader="DriveSafe", duration=420.0, platform="youtube"),
            CandidateResult(id="cand_weeknd_video", title="The Weeknd - Blinding Lights (Official Video)", uploader="TheWeekndVEVO", duration=263.0, platform="youtube"),
            CandidateResult(id="cand_weeknd_audio", title="The Weeknd - Blinding Lights (Audio)", uploader="TheWeekndVEVO", duration=202.0, platform="youtube"),
        ],
    },
    {
        "query_id": "tune_typo_03",
        "query": "get lukcy daft punk pharrel",
        "category": "incomplete_typos",
        "expected_relevant_ids": ["cand_daft_official"],
        "relevance_grades": {
            "cand_daft_official": 3,
            "cand_unrelated_lucky": 0,
        },
        "expected_artist": "Daft Punk",
        "expected_title": "Get Lucky",
        "candidate_pool": [
            CandidateResult(id="cand_unrelated_lucky", title="How to Get Lucky in Business: 5 Tips", uploader="BizSuccess", duration=600.0, platform="youtube"),
            CandidateResult(id="cand_daft_official", title="Daft Punk - Get Lucky (feat. Pharrell Williams)", uploader="Daft Punk", duration=248.0, platform="youtube"),
        ],
    },

    # 3. Natural Language, Lyrics & Contextual Clues
    {
        "query_id": "tune_lyrics_01",
        "query": "mama just killed a man put a gun against his head song",
        "category": "lyrics_context",
        "expected_relevant_ids": ["cand_queen_studio", "cand_queen_lyrics"],
        "relevance_grades": {
            "cand_queen_studio": 3,
            "cand_queen_lyrics": 2,
            "cand_crime_documentary": 0,
        },
        "expected_title": "Bohemian Rhapsody",
        "candidate_pool": [
            CandidateResult(id="cand_crime_documentary", title="True Crime Stories: Mama Just Killed a Man Documentary", uploader="CrimeInvestigate", duration=1200.0, platform="youtube"),
            CandidateResult(id="cand_queen_lyrics", title="Queen - Bohemian Rhapsody (Mama Just Killed a Man - Lyrics)", uploader="QueenLyrics", duration=355.0, platform="youtube"),
            CandidateResult(id="cand_queen_studio", title="Queen - Bohemian Rhapsody (Official Video)", uploader="Queen Official", duration=359.0, platform="youtube"),
        ],
    },
    {
        "query_id": "tune_lyrics_02",
        "query": "song with i said ooh i'm blinded by the lights",
        "category": "lyrics_context",
        "expected_relevant_ids": ["cand_weeknd_audio", "cand_weeknd_video"],
        "relevance_grades": {
            "cand_weeknd_audio": 3,
            "cand_weeknd_video": 3,
            "cand_driving_night": 0,
        },
        "expected_title": "Blinding Lights",
        "candidate_pool": [
            CandidateResult(id="cand_driving_night", title="Night Drive 4K Ambient Relaxing City Lights", uploader="CityVibes", duration=3600.0, platform="youtube"),
            CandidateResult(id="cand_weeknd_audio", title="The Weeknd - Blinding Lights (Lyrics: I said, ooh, I'm blinded by the lights)", uploader="PopLyrics", duration=202.0, platform="youtube"),
            CandidateResult(id="cand_weeknd_video", title="The Weeknd - Blinding Lights (Official Music Video)", uploader="TheWeekndVEVO", duration=263.0, platform="youtube"),
        ],
    },
    {
        "query_id": "tune_lyrics_03",
        "query": "we've come too far to give up who we are up all night to get lucky",
        "category": "lyrics_context",
        "expected_relevant_ids": ["cand_daft_official"],
        "relevance_grades": {
            "cand_daft_official": 3,
            "cand_motivational_speech": 0,
        },
        "expected_title": "Get Lucky",
        "candidate_pool": [
            CandidateResult(id="cand_motivational_speech", title="Don't Give Up Who You Are - Motivational Speech 2023", uploader="MotivationDaily", duration=480.0, platform="youtube"),
            CandidateResult(id="cand_daft_official", title="Daft Punk - Get Lucky (Lyrics: We've come too far to give up who we are)", uploader="Daft Punk Lyrics", duration=248.0, platform="youtube"),
        ],
    },

    # 4. Version Disambiguation (Remix, Live, Instrumental)
    {
        "query_id": "tune_version_01",
        "query": "The Weeknd Blinding Lights Chromatics remix",
        "category": "version_disambiguation",
        "expected_relevant_ids": ["cand_weeknd_chromatics"],
        "relevance_grades": {
            "cand_weeknd_chromatics": 3,
            "cand_weeknd_studio": 1,  # Studio version penalized when remix is requested
            "cand_weeknd_major_lazer": 1,
        },
        "expected_artist": "The Weeknd",
        "expected_title": "Blinding Lights (Chromatics Remix)",
        "candidate_pool": [
            CandidateResult(id="cand_weeknd_studio", title="The Weeknd - Blinding Lights (Official Audio)", uploader="TheWeekndVEVO", duration=202.0, platform="youtube"),
            CandidateResult(id="cand_weeknd_major_lazer", title="The Weeknd - Blinding Lights (Major Lazer Remix)", uploader="The Weeknd", duration=198.0, platform="youtube"),
            CandidateResult(id="cand_weeknd_chromatics", title="The Weeknd - Blinding Lights (Chromatics Remix) [Official Audio]", uploader="TheWeekndVEVO", duration=261.0, platform="youtube"),
        ],
    },
    {
        "query_id": "tune_version_02",
        "query": "Queen Bohemian Rhapsody Live Aid 1985",
        "category": "version_disambiguation",
        "expected_relevant_ids": ["cand_queen_live_aid"],
        "relevance_grades": {
            "cand_queen_live_aid": 3,
            "cand_queen_studio": 1,
            "cand_queen_budapest": 1,
        },
        "expected_artist": "Queen",
        "expected_title": "Bohemian Rhapsody (Live Aid 1985)",
        "candidate_pool": [
            CandidateResult(id="cand_queen_studio", title="Queen - Bohemian Rhapsody (Official Video)", uploader="Queen Official", duration=359.0, platform="youtube"),
            CandidateResult(id="cand_queen_budapest", title="Queen - Bohemian Rhapsody (Live In Budapest 1986)", uploader="Queen Official", duration=340.0, platform="youtube"),
            CandidateResult(id="cand_queen_live_aid", title="Queen - Bohemian Rhapsody (Live Aid 1985)", uploader="Queen Official", duration=385.0, platform="youtube"),
        ],
    },
    {
        "query_id": "tune_version_03",
        "query": "Daft Punk Get Lucky instrumental karaoke backing track",
        "category": "version_disambiguation",
        "expected_relevant_ids": ["cand_daft_instrumental"],
        "relevance_grades": {
            "cand_daft_instrumental": 3,
            "cand_daft_vocal": 1,
        },
        "expected_artist": "Daft Punk",
        "expected_title": "Get Lucky (Instrumental)",
        "candidate_pool": [
            CandidateResult(id="cand_daft_vocal", title="Daft Punk - Get Lucky (Official Vocal Track)", uploader="Daft Punk", duration=248.0, platform="youtube"),
            CandidateResult(id="cand_daft_instrumental", title="Daft Punk - Get Lucky (Official Instrumental Backing Track)", uploader="KaraokePro", duration=248.0, platform="youtube"),
        ],
    },

    # 5. Multilingual & Unicode Handling
    {
        "query_id": "tune_multi_01",
        "query": "Rosalia Despecha",
        "category": "multilingual_unicode",
        "expected_relevant_ids": ["cand_rosalia_despecha"],
        "relevance_grades": {
            "cand_rosalia_despecha": 3,
            "cand_rosalia_motomami": 1,
            "cand_unrelated_spanish": 0,
        },
        "expected_artist": "ROSALÍA",
        "expected_title": "DESPECHÁ",
        "candidate_pool": [
            CandidateResult(id="cand_unrelated_spanish", title="Aprende Español en 15 Minutos", uploader="LearnSpanish", duration=900.0, platform="youtube"),
            CandidateResult(id="cand_rosalia_motomami", title="ROSALÍA - MOTOMAMI (Official Album Audio)", uploader="RosaliaVEVO", duration=60.0, platform="youtube"),
            CandidateResult(id="cand_rosalia_despecha", title="ROSALÍA - DESPECHÁ (Video Oficial)", uploader="RosaliaVEVO", duration=157.0, platform="youtube"),
        ],
    },
    {
        "query_id": "tune_multi_02",
        "query": "宇多田ヒカル First Love",
        "category": "multilingual_unicode",
        "expected_relevant_ids": ["cand_utada_firstlove"],
        "relevance_grades": {
            "cand_utada_firstlove": 3,
            "cand_utada_automatic": 1,
        },
        "expected_artist": "宇多田ヒカル",
        "expected_title": "First Love",
        "candidate_pool": [
            CandidateResult(id="cand_utada_automatic", title="宇多田ヒカル - Automatic (Official Music Video)", uploader="HikaruUtadaVEVO", duration=320.0, platform="youtube"),
            CandidateResult(id="cand_utada_firstlove", title="宇多田ヒカル - First Love (4K Remastered)", uploader="HikaruUtadaVEVO", duration=262.0, platform="youtube"),
        ],
    },
    {
        "query_id": "tune_multi_03",
        "query": "Stromae Alors on danse",
        "category": "multilingual_unicode",
        "expected_relevant_ids": ["cand_stromae_danse"],
        "relevance_grades": {
            "cand_stromae_danse": 3,
            "cand_stromae_papaoutai": 1,
        },
        "expected_artist": "Stromae",
        "expected_title": "Alors on danse",
        "candidate_pool": [
            CandidateResult(id="cand_stromae_papaoutai", title="Stromae - Papaoutai (Clip Officiel)", uploader="StromaeVEVO", duration=232.0, platform="youtube"),
            CandidateResult(id="cand_stromae_danse", title="Stromae - Alors on danse (Clip Officiel)", uploader="StromaeVEVO", duration=214.0, platform="youtube"),
        ],
    },

    # 6. Negative & Unanswerable Queries (Should yield no high confidence match)
    {
        "query_id": "tune_negative_01",
        "query": "zxqwv9923 completely non-existent audio track 12345",
        "category": "negative_unanswerable",
        "expected_relevant_ids": [],
        "relevance_grades": {
            "cand_junk_01": 0,
            "cand_junk_02": 0,
        },
        "candidate_pool": [
            CandidateResult(id="cand_junk_01", title="Random Test Noise Video #442", uploader="RandomUser", duration=12.0, platform="youtube"),
            CandidateResult(id="cand_junk_02", title="Unrelated Tech Talk", uploader="DevChannel", duration=1800.0, platform="youtube"),
        ],
    },
    {
        "query_id": "tune_negative_02",
        "query": "fabricated gibberish query 0000_not_found_song",
        "category": "negative_unanswerable",
        "expected_relevant_ids": [],
        "relevance_grades": {
            "cand_junk_03": 0,
        },
        "candidate_pool": [
            CandidateResult(id="cand_junk_03", title="10 Hours of Brown Noise", uploader="RelaxSounds", duration=36000.0, platform="youtube"),
        ],
    },
    {
        "query_id": "tune_negative_03",
        "query": "qwertyuiopasdfghjklzxcvbnm invalid sound effect",
        "category": "negative_unanswerable",
        "expected_relevant_ids": [],
        "relevance_grades": {
            "cand_junk_04": 0,
        },
        "candidate_pool": [
            CandidateResult(id="cand_junk_04", title="Keyboard Typing Sound Effects ASMR", uploader="ASMRTyping", duration=600.0, platform="youtube"),
        ],
    },
]

# HELD-OUT EVALUATION SET: Strictly preserved, never tuned on!
HELD_OUT_QUERIES: List[Dict[str, Any]] = [
    # 1. Exact
    {
        "query_id": "held_exact_01",
        "query": "Billie Eilish Bad Guy",
        "category": "exact",
        "expected_relevant_ids": ["cand_billie_badguy", "cand_billie_audio"],
        "relevance_grades": {
            "cand_billie_badguy": 3,
            "cand_billie_audio": 3,
            "cand_billie_cover": 0,
            "cand_billie_live": 1,
        },
        "expected_artist": "Billie Eilish",
        "expected_title": "bad guy",
        "ideal_duration": 194.0,
        "candidate_pool": [
            CandidateResult(id="cand_billie_cover", title="bad guy - Billie Eilish (Ukulele Cover)", uploader="UkeBoy", duration=180.0, platform="youtube"),
            CandidateResult(id="cand_billie_live", title="Billie Eilish - bad guy (Live at Coachella)", uploader="Coachella", duration=210.0, platform="youtube"),
            CandidateResult(id="cand_billie_audio", title="Billie Eilish - bad guy (Audio)", uploader="BillieEilishVEVO", duration=194.0, platform="youtube"),
            CandidateResult(id="cand_billie_badguy", title="Billie Eilish - bad guy (Official Music Video)", uploader="BillieEilishVEVO", duration=205.0, platform="youtube"),
        ],
    },
    {
        "query_id": "held_exact_02",
        "query": "Eminem Lose Yourself",
        "category": "exact",
        "expected_relevant_ids": ["cand_eminem_official", "cand_eminem_audio"],
        "relevance_grades": {
            "cand_eminem_official": 3,
            "cand_eminem_audio": 3,
            "cand_eminem_live": 1,
            "cand_eminem_parody": 0,
        },
        "expected_artist": "Eminem",
        "expected_title": "Lose Yourself",
        "ideal_duration": 326.0,
        "candidate_pool": [
            CandidateResult(id="cand_eminem_parody", title="Lose Yourself Mom's Spaghetti Parody", uploader="ComedyRap", duration=240.0, platform="youtube"),
            CandidateResult(id="cand_eminem_live", title="Eminem - Lose Yourself (Live at the Oscars)", uploader="Oscars", duration=340.0, platform="youtube"),
            CandidateResult(id="cand_eminem_audio", title="Eminem - Lose Yourself (Official Audio)", uploader="EminemMusic", duration=326.0, platform="youtube"),
            CandidateResult(id="cand_eminem_official", title="Eminem - Lose Yourself [Official Music Video - HD]", uploader="EminemMusic", duration=326.0, platform="youtube"),
        ],
    },

    # 2. Typos
    {
        "query_id": "held_typo_01",
        "query": "bili eilesh bd guy",
        "category": "incomplete_typos",
        "expected_relevant_ids": ["cand_billie_badguy", "cand_billie_audio"],
        "relevance_grades": {
            "cand_billie_badguy": 3,
            "cand_billie_audio": 3,
            "cand_unrelated_guy": 0,
        },
        "expected_artist": "Billie Eilish",
        "expected_title": "bad guy",
        "candidate_pool": [
            CandidateResult(id="cand_unrelated_guy", title="How to Be a Good Guy vs Bad Guy", uploader="LifeAdvice", duration=700.0, platform="youtube"),
            CandidateResult(id="cand_billie_audio", title="Billie Eilish - bad guy (Audio)", uploader="BillieEilishVEVO", duration=194.0, platform="youtube"),
            CandidateResult(id="cand_billie_badguy", title="Billie Eilish - bad guy (Official Music Video)", uploader="BillieEilishVEVO", duration=205.0, platform="youtube"),
        ],
    },
    {
        "query_id": "held_typo_02",
        "query": "eminm lose youreself 8 mile",
        "category": "incomplete_typos",
        "expected_relevant_ids": ["cand_eminem_official", "cand_eminem_audio"],
        "relevance_grades": {
            "cand_eminem_official": 3,
            "cand_eminem_audio": 3,
            "cand_unrelated_running": 0,
        },
        "expected_artist": "Eminem",
        "expected_title": "Lose Yourself",
        "candidate_pool": [
            CandidateResult(id="cand_unrelated_running", title="Lose Weight Running 8 Miles", uploader="FitRun", duration=900.0, platform="youtube"),
            CandidateResult(id="cand_eminem_audio", title="Eminem - Lose Yourself (From 8 Mile Soundtrack)", uploader="EminemMusic", duration=326.0, platform="youtube"),
            CandidateResult(id="cand_eminem_official", title="Eminem - Lose Yourself (Official Video)", uploader="EminemMusic", duration=326.0, platform="youtube"),
        ],
    },

    # 3. Lyrics / Context
    {
        "query_id": "held_lyrics_01",
        "query": "so you're a tough guy like it really rough guy",
        "category": "lyrics_context",
        "expected_relevant_ids": ["cand_billie_badguy", "cand_billie_audio"],
        "relevance_grades": {
            "cand_billie_badguy": 3,
            "cand_billie_audio": 3,
            "cand_boxing_workout": 0,
        },
        "expected_title": "bad guy",
        "candidate_pool": [
            CandidateResult(id="cand_boxing_workout", title="Tough Guy Boxing Workout Routine", uploader="BoxingCamp", duration=1500.0, platform="youtube"),
            CandidateResult(id="cand_billie_audio", title="Billie Eilish - bad guy (Lyrics: So you're a tough guy, like it really rough guy)", uploader="PopLyrics", duration=194.0, platform="youtube"),
            CandidateResult(id="cand_billie_badguy", title="Billie Eilish - bad guy (Official Video)", uploader="BillieEilishVEVO", duration=205.0, platform="youtube"),
        ],
    },
    {
        "query_id": "held_lyrics_02",
        "query": "his palms are sweaty knees weak arms are heavy mom's spaghetti",
        "category": "lyrics_context",
        "expected_relevant_ids": ["cand_eminem_official", "cand_eminem_audio"],
        "relevance_grades": {
            "cand_eminem_official": 3,
            "cand_eminem_audio": 3,
            "cand_cooking_pasta": 0,
        },
        "expected_title": "Lose Yourself",
        "candidate_pool": [
            CandidateResult(id="cand_cooking_pasta", title="How to Cook Perfect Spaghetti Like Mom", uploader="ItalianChef", duration=480.0, platform="youtube"),
            CandidateResult(id="cand_eminem_audio", title="Eminem - Lose Yourself (Lyrics: His palms are sweaty...)", uploader="EminemMusic", duration=326.0, platform="youtube"),
            CandidateResult(id="cand_eminem_official", title="Eminem - Lose Yourself (Official Video)", uploader="EminemMusic", duration=326.0, platform="youtube"),
        ],
    },

    # 4. Version Disambiguation
    {
        "query_id": "held_version_01",
        "query": "Billie Eilish bad guy remix featuring Justin Bieber",
        "category": "version_disambiguation",
        "expected_relevant_ids": ["cand_billie_bieber"],
        "relevance_grades": {
            "cand_billie_bieber": 3,
            "cand_billie_original": 1,
        },
        "expected_artist": "Billie Eilish",
        "expected_title": "bad guy (with Justin Bieber)",
        "candidate_pool": [
            CandidateResult(id="cand_billie_original", title="Billie Eilish - bad guy (Official Audio)", uploader="BillieEilishVEVO", duration=194.0, platform="youtube"),
            CandidateResult(id="cand_billie_bieber", title="Billie Eilish - bad guy (with Justin Bieber) [Official Audio]", uploader="BillieEilishVEVO", duration=194.0, platform="youtube"),
        ],
    },
    {
        "query_id": "held_version_02",
        "query": "Eminem Lose Yourself official instrumental track",
        "category": "version_disambiguation",
        "expected_relevant_ids": ["cand_eminem_inst"],
        "relevance_grades": {
            "cand_eminem_inst": 3,
            "cand_eminem_vocal": 1,
        },
        "expected_artist": "Eminem",
        "expected_title": "Lose Yourself (Instrumental)",
        "candidate_pool": [
            CandidateResult(id="cand_eminem_vocal", title="Eminem - Lose Yourself (Official Video)", uploader="EminemMusic", duration=326.0, platform="youtube"),
            CandidateResult(id="cand_eminem_inst", title="Eminem - Lose Yourself (Official Instrumental)", uploader="EminemMusic", duration=326.0, platform="youtube"),
        ],
    },

    # 5. Multilingual
    {
        "query_id": "held_multi_01",
        "query": "Rammstein Du Hast",
        "category": "multilingual_unicode",
        "expected_relevant_ids": ["cand_rammstein_duhast"],
        "relevance_grades": {
            "cand_rammstein_duhast": 3,
            "cand_rammstein_sonne": 1,
        },
        "expected_artist": "Rammstein",
        "expected_title": "Du Hast",
        "candidate_pool": [
            CandidateResult(id="cand_rammstein_sonne", title="Rammstein - Sonne (Official Video)", uploader="Rammstein Official", duration=252.0, platform="youtube"),
            CandidateResult(id="cand_rammstein_duhast", title="Rammstein - Du Hast (Official 4K Remastered)", uploader="Rammstein Official", duration=235.0, platform="youtube"),
        ],
    },
    {
        "query_id": "held_multi_02",
        "query": "Stromae Papaoutai",
        "category": "multilingual_unicode",
        "expected_relevant_ids": ["cand_stromae_papaoutai"],
        "relevance_grades": {
            "cand_stromae_papaoutai": 3,
            "cand_stromae_danse": 1,
        },
        "expected_artist": "Stromae",
        "expected_title": "Papaoutai",
        "candidate_pool": [
            CandidateResult(id="cand_stromae_danse", title="Stromae - Alors on danse (Clip Officiel)", uploader="StromaeVEVO", duration=214.0, platform="youtube"),
            CandidateResult(id="cand_stromae_papaoutai", title="Stromae - Papaoutai (Clip Officiel)", uploader="StromaeVEVO", duration=232.0, platform="youtube"),
        ],
    },

    # 6. Negative
    {
        "query_id": "held_negative_01",
        "query": "completely fabricated nonsense title 999111888",
        "category": "negative_unanswerable",
        "expected_relevant_ids": [],
        "relevance_grades": {
            "cand_junk_held_1": 0,
        },
        "candidate_pool": [
            CandidateResult(id="cand_junk_held_1", title="Sample Static Video 001", uploader="StaticChannel", duration=15.0, platform="youtube"),
        ],
    },
    {
        "query_id": "held_negative_02",
        "query": "zzzzqqqqxxx non-existent track title",
        "category": "negative_unanswerable",
        "expected_relevant_ids": [],
        "relevance_grades": {
            "cand_junk_held_2": 0,
        },
        "candidate_pool": [
            CandidateResult(id="cand_junk_held_2", title="Unrelated Drone Video 4K", uploader="DroneFly", duration=300.0, platform="youtube"),
        ],
    },
]
