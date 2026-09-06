# Repository Coverage

[Full report](https://zacker150.github.io/discord-ext-voice-recv/htmlcov/index.html)

| Name                                                |    Stmts |     Miss |   Branch |   BrPart |   Cover |   Missing |
|---------------------------------------------------- | -------: | -------: | -------: | -------: | ------: | --------: |
| discord/ext/voice\_recv/buffer.py                   |      127 |       12 |       36 |        6 |     89% |53, 59, 62, 65, 68-70, 73, 176, 181-\>184, 209, 223, 244, 257-\>260 |
| discord/ext/voice\_recv/dave.py                     |       98 |        2 |       20 |        2 |     97% |  103, 113 |
| discord/ext/voice\_recv/extras/localplayback.py     |       64 |       54 |       20 |        0 |     12% |    28-132 |
| discord/ext/voice\_recv/extras/speechrecognition.py |      132 |      123 |       30 |        0 |      6% |    20-237 |
| discord/ext/voice\_recv/gateway.py                  |       70 |        6 |       30 |        3 |     91% |52-\>61, 110-112, 115-117 |
| discord/ext/voice\_recv/opus.py                     |      189 |       87 |       40 |       10 |     50% |48, 72-\>exit, 77-\>exit, 96-\>exit, 119-121, 150-151, 154, 157-160, 163-164, 167-173, 176, 179-182, 185-187, 206-210, 218-232, 240-242, 246-248, 256-260, 277-366 |
| discord/ext/voice\_recv/reader.py                   |      834 |      544 |      244 |       20 |     32% |24-25, 65-81, 84-87, 90-92, 96-100, 104-107, 110-114, 124-130, 133-152, 155-215, 229-245, 248-254, 257-327, 330-333, 347-360, 377-404, 419-434, 441-455, 458-501, 513-555, 558, 561, 564-573, 576-584, 587-613, 620-626, 656-676, 715, 739-740, 752-\>755, 774-793, 835, 858-859, 862-863, 865, 869-\>exit, 879-882, 905-906, 921, 924, 927, 931, 934-935, 948, 977-1001, 1010-1069, 1072-1078, 1082, 1092-1093, 1097-1098, 1105-\>1112, 1131-1132, 1142-1143, 1148-1152, 1160-1161, 1166-1170, 1179-1180, 1185-1190, 1193-1291, 1294-1301, 1305-1313, 1316-1317, 1320-1322, 1325-1328, 1331-1337, 1340-1344, 1347, 1350-1351, 1354-1384, 1392-1398, 1401-1422, 1425 |
| discord/ext/voice\_recv/router.py                   |      145 |       11 |       36 |        3 |     92% |50-\>exit, 83-\>exit, 168-\>165, 171-172, 183, 186-191, 197-198 |
| discord/ext/voice\_recv/rtp.py                      |      284 |       13 |       58 |        5 |     95% |67, 83, 120, 137, 235-\>238, 243, 275, 287, 294-295, 298, 325-326, 358-\>exit, 458 |
| discord/ext/voice\_recv/silence.py                  |       88 |       66 |       20 |        0 |     20% |39-48, 56-63, 66, 73-86, 91-100, 103-104, 107-110, 113-152 |
| discord/ext/voice\_recv/sinks.py                    |      379 |       90 |       70 |       12 |     76% |101, 106, 111, 116, 121, 128, 133, 137, 141, 189, 196, 213, 219, 242-\>exit, 248, 304-309, 312, 315, 318-321, 372, 376-380, 411-415, 418-422, 426, 436-\>exit, 451-455, 469-470, 476-477, 481-482, 485-487, 494-513, 534, 563, 570, 593, 610, 617-621, 624, 627-628, 632, 635 |
| discord/ext/voice\_recv/types.py                    |       34 |       34 |        0 |        0 |      0% |      3-59 |
| discord/ext/voice\_recv/utils.py                    |      129 |        5 |       22 |        1 |     96% |51, 66, 102-103, 134 |
| discord/ext/voice\_recv/video.py                    |       41 |        3 |        0 |        0 |     93% | 35, 41-42 |
| discord/ext/voice\_recv/voice\_client.py            |      221 |       52 |       82 |       12 |     77% |42-54, 67-82, 91, 98-\>exit, 101-102, 105-110, 113-114, 135-\>147, 138, 144, 152, 157-\>163, 192, 205-207, 227-\>231, 245, 261, 269, 272, 311-313, 317-319, 323-324, 347-\>exit |
| **TOTAL**                                           | **2871** | **1102** |  **708** |   **74** | **60%** |           |

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