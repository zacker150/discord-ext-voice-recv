# Repository Coverage

[Full report](https://zacker150.github.io/discord-ext-voice-recv/htmlcov/index.html)

| Name                                                |    Stmts |     Miss |   Branch |   BrPart |   Cover |   Missing |
|---------------------------------------------------- | -------: | -------: | -------: | -------: | ------: | --------: |
| discord/ext/voice\_recv/buffer.py                   |      127 |       12 |       36 |        6 |     89% |53, 59, 62, 65, 68-70, 73, 176, 181-\>184, 209, 223, 244, 257-\>260 |
| discord/ext/voice\_recv/dave.py                     |      107 |        2 |       24 |        2 |     97% |  115, 125 |
| discord/ext/voice\_recv/extras/localplayback.py     |       64 |       54 |       20 |        0 |     12% |    28-132 |
| discord/ext/voice\_recv/extras/speechrecognition.py |      132 |      123 |       30 |        0 |      6% |    20-237 |
| discord/ext/voice\_recv/gateway.py                  |       76 |        6 |       34 |        3 |     92% |57-\>66, 116-118, 121-123 |
| discord/ext/voice\_recv/opus.py                     |      189 |       87 |       40 |       10 |     50% |48, 72-\>exit, 77-\>exit, 96-\>exit, 119-121, 150-151, 154, 157-160, 163-164, 167-173, 176, 179-182, 185-187, 206-210, 218-232, 240-242, 246-248, 256-260, 277-366 |
| discord/ext/voice\_recv/reader.py                   |      875 |      434 |      258 |       31 |     48% |24-25, 79-81, 85, 91, 96-100, 104-107, 113-114, 124-130, 133-152, 155-215, 229-245, 248-254, 263-324, 377-404, 419-434, 441-455, 458-501, 513-559, 562, 565, 568-580, 583-593, 596-624, 631-637, 667-687, 726, 750-751, 763-\>766, 785-804, 820-\>exit, 829-833, 869, 892-893, 896-897, 899, 903-\>exit, 909, 915-918, 941-942, 956, 959, 962-963, 970-971, 1034, 1037-\>1039, 1076, 1103-1104, 1108-1109, 1114, 1144-1145, 1155-1156, 1161-1165, 1173-1174, 1179-1183, 1192-1193, 1198-1203, 1213-1215, 1244-1245, 1247-1248, 1252-1259, 1263-1271, 1274-1275, 1278-1280, 1283-1286, 1289-1295, 1298-1302, 1305, 1308-1309, 1312-1342, 1350-1356, 1359-1380, 1383 |
| discord/ext/voice\_recv/router.py                   |      145 |       11 |       36 |        3 |     92% |50-\>exit, 83-\>exit, 168-\>165, 171-172, 183, 186-191, 197-198 |
| discord/ext/voice\_recv/rtp.py                      |      284 |       13 |       58 |        5 |     95% |67, 83, 120, 137, 235-\>238, 243, 275, 287, 294-295, 298, 325-326, 358-\>exit, 458 |
| discord/ext/voice\_recv/silence.py                  |       88 |       66 |       20 |        0 |     20% |39-48, 56-63, 66, 73-86, 91-100, 103-104, 107-110, 113-152 |
| discord/ext/voice\_recv/sinks.py                    |      379 |       90 |       70 |       12 |     76% |101, 106, 111, 116, 121, 128, 133, 137, 141, 189, 196, 213, 219, 242-\>exit, 248, 304-309, 312, 315, 318-321, 372, 376-380, 411-415, 418-422, 426, 436-\>exit, 451-455, 469-470, 476-477, 481-482, 485-487, 494-513, 534, 563, 570, 593, 610, 617-621, 624, 627-628, 632, 635 |
| discord/ext/voice\_recv/types.py                    |       34 |       34 |        0 |        0 |      0% |      3-59 |
| discord/ext/voice\_recv/utils.py                    |      129 |        5 |       22 |        1 |     96% |51, 66, 102-103, 134 |
| discord/ext/voice\_recv/video.py                    |       41 |        3 |        0 |        0 |     93% | 35, 41-42 |
| discord/ext/voice\_recv/voice\_client.py            |      228 |       54 |       84 |       12 |     77% |42-54, 72-73, 76-91, 100, 107-\>exit, 110-111, 114-119, 122-123, 144-\>156, 147, 153, 161, 166-\>172, 201, 214-216, 236-\>240, 254, 270, 278, 281, 320-322, 326-328, 332-333, 356-\>exit |
| **TOTAL**                                           | **2934** |  **994** |  **732** |   **85** | **65%** |           |

3 files skipped due to complete coverage.


## Setup coverage badge

Below are examples of the badges you can use in your main branch `README` file.

### Direct image

[![Coverage badge](https://raw.githubusercontent.com/zacker150/discord-ext-voice-recv/python-coverage-comment-action-data/badge.svg)](https://zacker150.github.io/discord-ext-voice-recv/htmlcov/index.html)

This is the one to use if your repository is private or if you don't want to customize anything.

### [Shields.io](https://shields.io) Json Endpoint

[![Coverage badge](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/zacker150/discord-ext-voice-recv/python-coverage-comment-action-data/endpoint.json)](https://zacker150.github.io/discord-ext-voice-recv/htmlcov/index.html)

Using this one will allow you to [customize](https://shields.io/endpoint) the look of your badge.
It won't work with private repositories. It won't be refreshed more than once per five minutes.

### [Shields.io](https://shields.io) Dynamic Badge

[![Coverage badge](https://img.shields.io/badge/dynamic/json?color=brightgreen&label=coverage&query=%24.message&url=https%3A%2F%2Fraw.githubusercontent.com%2Fzacker150%2Fdiscord-ext-voice-recv%2Fpython-coverage-comment-action-data%2Fendpoint.json)](https://zacker150.github.io/discord-ext-voice-recv/htmlcov/index.html)

This one will always be the same color. It won't work for private repos. I'm not even sure why we included it.

## What is that?

This branch is part of the
[python-coverage-comment-action](https://github.com/marketplace/actions/python-coverage-comment)
GitHub Action. All the files in this branch are automatically generated and may be
overwritten at any moment.