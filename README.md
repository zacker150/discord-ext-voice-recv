# Repository Coverage

[Full report](https://zacker150.github.io/discord-ext-voice-recv/htmlcov/index.html)

| Name                                                |    Stmts |     Miss |   Branch |   BrPart |   Cover |   Missing |
|---------------------------------------------------- | -------: | -------: | -------: | -------: | ------: | --------: |
| discord/ext/voice\_recv/buffer.py                   |      127 |       12 |       36 |        6 |     89% |53, 59, 62, 65, 68-70, 73, 176, 181-\>184, 209, 223, 244, 257-\>260 |
| discord/ext/voice\_recv/dave.py                     |       56 |        2 |       16 |        2 |     94% |    33, 43 |
| discord/ext/voice\_recv/extras/localplayback.py     |       64 |       54 |       20 |        0 |     12% |    28-132 |
| discord/ext/voice\_recv/extras/speechrecognition.py |      132 |      123 |       30 |        0 |      6% |    20-237 |
| discord/ext/voice\_recv/gateway.py                  |      126 |       82 |       38 |        0 |     27% |82-114, 118-198 |
| discord/ext/voice\_recv/opus.py                     |      189 |       87 |       40 |       10 |     50% |48, 72-\>exit, 77-\>exit, 96-\>exit, 119-121, 150-151, 154, 157-160, 163-164, 167-173, 176, 179-182, 185-187, 206-210, 218-232, 240-242, 246-248, 256-260, 277-366 |
| discord/ext/voice\_recv/reader.py                   |      850 |      591 |      246 |       14 |     28% |23-24, 29-30, 70-86, 89-92, 95-97, 101-105, 109-112, 115-119, 129-135, 138-157, 160-220, 234-250, 253-259, 262-332, 335-338, 352-365, 382-409, 424-439, 446-460, 463-506, 518-560, 563, 566, 569-578, 581-589, 592-618, 625-631, 661-681, 720, 744-745, 757-\>760, 779-798, 840, 863-864, 867-868, 870, 874-\>exit, 884-887, 906-920, 923-926, 929, 932, 935-936, 939-940, 952-953, 966, 981-1005, 1014-1073, 1076-1082, 1086, 1095-1144, 1157-1158, 1168-1169, 1174-1178, 1186-1187, 1192-1196, 1205-1206, 1211-1216, 1219-1317, 1320-1327, 1331-1339, 1342-1343, 1346-1348, 1351-1354, 1357-1363, 1366-1370, 1373, 1376-1377, 1380-1410, 1418-1424, 1427-1448, 1451 |
| discord/ext/voice\_recv/router.py                   |      145 |       11 |       36 |        3 |     92% |50-\>exit, 83-\>exit, 168-\>165, 171-172, 183, 186-191, 197-198 |
| discord/ext/voice\_recv/rtp.py                      |      284 |       13 |       58 |        5 |     95% |67, 83, 120, 137, 235-\>238, 243, 275, 287, 294-295, 298, 325-326, 358-\>exit, 458 |
| discord/ext/voice\_recv/silence.py                  |       88 |       66 |       20 |        0 |     20% |39-48, 56-63, 66, 73-86, 91-100, 103-104, 107-110, 113-152 |
| discord/ext/voice\_recv/sinks.py                    |      379 |       90 |       70 |       12 |     76% |101, 106, 111, 116, 121, 128, 133, 137, 141, 189, 196, 213, 219, 242-\>exit, 248, 304-309, 312, 315, 318-321, 372, 376-380, 411-415, 418-422, 426, 436-\>exit, 451-455, 469-470, 476-477, 481-482, 485-487, 494-513, 534, 563, 570, 593, 610, 617-621, 624, 627-628, 632, 635 |
| discord/ext/voice\_recv/types.py                    |       34 |       34 |        0 |        0 |      0% |      3-59 |
| discord/ext/voice\_recv/utils.py                    |      129 |        5 |       22 |        1 |     96% |51, 66, 102-103, 134 |
| discord/ext/voice\_recv/video.py                    |       41 |        3 |        0 |        0 |     93% | 35, 41-42 |
| discord/ext/voice\_recv/voice\_client.py            |      216 |       65 |       80 |       12 |     69% |40-52, 55-56, 59-74, 83, 90-\>exit, 93-94, 97-102, 105-106, 119-120, 127-\>139, 130, 136, 144, 147-162, 184, 197-199, 219-\>223, 237, 246-\>248, 253, 261, 264, 303-305, 309-311, 315-316, 339-\>exit |
| **TOTAL**                                           | **2896** | **1238** |  **712** |   **65** | **55%** |           |

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