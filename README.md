# Repository Coverage

[Full report](https://zacker150.github.io/discord-ext-voice-recv/htmlcov/index.html)

| Name                                                |    Stmts |     Miss |   Branch |   BrPart |   Cover |   Missing |
|---------------------------------------------------- | -------: | -------: | -------: | -------: | ------: | --------: |
| discord/ext/voice\_recv/buffer.py                   |      127 |       12 |       36 |        6 |     89% |53, 59, 62, 65, 68-70, 73, 176, 181-\>184, 209, 223, 244, 257-\>260 |
| discord/ext/voice\_recv/dave.py                     |      133 |        3 |       34 |        3 |     96% |122, 160, 170 |
| discord/ext/voice\_recv/extras/localplayback.py     |       64 |       54 |       20 |        0 |     12% |    28-132 |
| discord/ext/voice\_recv/extras/speechrecognition.py |      132 |      123 |       30 |        0 |      6% |    20-237 |
| discord/ext/voice\_recv/gateway.py                  |       78 |        6 |       34 |        4 |     91% |59-\>68, 75-\>77, 120-122, 125-127 |
| discord/ext/voice\_recv/opus.py                     |      189 |       87 |       40 |       10 |     50% |48, 72-\>exit, 77-\>exit, 96-\>exit, 119-121, 150-151, 154, 157-160, 163-164, 167-173, 176, 179-182, 185-187, 206-210, 218-232, 240-242, 246-248, 256-260, 277-366 |
| discord/ext/voice\_recv/reader.py                   |      905 |      407 |      268 |       35 |     52% |25-26, 81-83, 87, 93, 98-102, 106-109, 115-116, 126-132, 135-154, 157-217, 231-247, 250-256, 265-326, 379-406, 421-436, 443-457, 480-483, 491-494, 503-\>505, 517-565, 568, 571, 574-586, 589-599, 602-630, 637-643, 673-693, 732, 756-757, 769-\>772, 791-810, 826-827, 830-831, 834-\>exit, 843-847, 883, 906-907, 910-911, 913, 917-\>exit, 923, 929-932, 955-956, 979, 982, 985-986, 993-994, 1057, 1068-\>1070, 1072-\>1074, 1111, 1139-1140, 1144-1145, 1150, 1180-1181, 1191-1192, 1197-1201, 1209-1210, 1215-1219, 1228-1229, 1234-1239, 1249-1251, 1280-1281, 1283-1284, 1288-1295, 1299-1307, 1310-1311, 1314-1316, 1319-1322, 1325-1331, 1334-1338, 1341, 1344-1345, 1348-1378, 1386-1392, 1395-1416, 1419 |
| discord/ext/voice\_recv/router.py                   |      145 |       11 |       36 |        3 |     92% |50-\>exit, 83-\>exit, 168-\>165, 171-172, 183, 186-191, 197-198 |
| discord/ext/voice\_recv/rtp.py                      |      284 |       13 |       58 |        5 |     95% |67, 83, 120, 137, 235-\>238, 243, 275, 287, 294-295, 298, 325-326, 358-\>exit, 458 |
| discord/ext/voice\_recv/silence.py                  |       88 |       66 |       20 |        0 |     20% |39-48, 56-63, 66, 73-86, 91-100, 103-104, 107-110, 113-152 |
| discord/ext/voice\_recv/sinks.py                    |      379 |       89 |       70 |       12 |     76% |101, 106, 111, 116, 121, 128, 133, 137, 141, 189, 196, 213, 219, 242-\>exit, 248, 304-309, 312, 315, 318-321, 372, 376-380, 411-415, 418-422, 426, 436-\>exit, 451-455, 469-470, 476-477, 481-482, 485-487, 494-513, 534, 563, 593, 610, 617-621, 624, 627-628, 632, 635 |
| discord/ext/voice\_recv/types.py                    |       34 |       34 |        0 |        0 |      0% |      3-59 |
| discord/ext/voice\_recv/utils.py                    |      129 |        5 |       22 |        1 |     96% |51, 66, 102-103, 134 |
| discord/ext/voice\_recv/video.py                    |       41 |        3 |        0 |        0 |     93% | 35, 41-42 |
| discord/ext/voice\_recv/voice\_client.py            |      260 |       51 |       94 |       13 |     80% |42-54, 75-\>80, 90-91, 103-119, 128, 135-\>exit, 138-139, 142-147, 150-151, 172-\>184, 175, 181, 189, 194-\>200, 229, 246, 278-\>282, 296, 312, 320, 323, 362-364, 368-370, 399-\>exit |
| **TOTAL**                                           | **3025** |  **964** |  **762** |   **92** | **66%** |           |

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