# US-China Official Diplomatic and Defense Corpus

This dataset provides a large-scale, systematically collected corpus of official diplomatic texts released by the governments of China and the United States between January 2021 and December 2025.

It is designed to support empirical research in international relations, political economy, strategic communication, computational social science, and natural language processing.

The corpus consists exclusively of publicly available, authoritative government communications, covering diplomacy, security, foreign policy, and international cooperation.

Dataset Link: https://zenodo.org/records/18383270

# Dataset Overview

## English

This repository contains data collected from multiple sources, including the **White House**, **Ministries of Foreign Affairs and National Defense of China**, and the **U.S. State Department**. The data primarily consists of **press briefings**, **news releases**, and **statements** from these organizations. The dataset is available in multiple formats (CSV, JSONL, and XLSX), providing flexibility for different data analysis needs.

### Files in this repository:

1. **Biden White House Website**: Contains press briefing data from the Biden White House, including press conferences and releases.
2. **Ministry of Foreign Affairs of China**: Contains press conference data from the Ministry of Foreign Affairs of China.
3. **Ministry of National Defense of China**: Contains press releases, press conferences, and transcripts from the Ministry of National Defense of China.
4. **Trump White House Website**: Contains news data from the Trump White House, including press releases and briefings.
5. **U.S. Department of State**: Contains press releases and briefings from the U.S. State Department, spanning the years 2021 to 2025.

### Dataset Fields:

The dataset includes the following fields:

1. **publish_time**: The publication date of the briefing or release.
2. **type**: The type of briefing or release (e.g., regular press briefing, spokesperson remarks).
3. **title**: The title of the briefing or release.
4. **content**: The main content or body of the briefing, which may include questions and answers (Q&A).
5. **source_url**: The URL where the briefing or release can be found on the respective official website.

### Files and Their Uses:

- **CSV Files**: These files contain tabular data and are compatible with Excel or any software that supports CSV files. They are often used for data analysis.
- **JSONL Files**: Each line of these files is a JSON object, representing a single record, which is suitable for data processing in programming tasks.
- **XLSX Files**: These files are the Excel versions of the CSV files, useful for users who prefer working with Excel.

### Detailed Description of Each File:

#### Biden White House Website:
- **biden_briefing_room_data_final.csv**: Contains the press briefing data in CSV format. Each row represents one press briefing, with metadata such as title, date, type, and content.
- **biden_briefing_room_data_final.jsonl**: Same data as the CSV but stored in JSONL format. Each line is a JSON object, representing one briefing.
- **biden_briefing_room_data_final.xlsx**: Contains the same data as the CSV file, formatted for use in Excel.

#### Ministry of Foreign Affairs of China (An early backup of crawler data, which may contain information that has been deleted from the current website):
- **国防部_专题记者会.xlsx**: Press conference data from the Ministry of National Defense of China in XLSX format.
- **国防部_例行记者会.xlsx**: Regular press conference data from the Ministry of National Defense of China.
- **国防部_例行新闻发布会.xlsx**: Regular news release data from the Ministry of National Defense of China.
- **国防部_例行记者会实录.xlsx**: Transcript data from the regular press conferences of the Ministry of National Defense of China.
- **外交部_例行记者会数据.xlsx**: Press conference data from the Ministry of Foreign Affairs of China.
- **国防部_发言人谈话和答记者问.xlsx**: Spokesperson remarks and Q&A from the Ministry of National Defense of China.

#### Ministry of National Defense of China:
- **mod_regular_news_briefings.csv**: CSV data containing regular press briefing information from the Ministry of National Defense of China.
- **mod_regular_news_briefings.jsonl**: JSONL data representing the same information as the CSV.
- **mod_regular_news_briefings.xlsx**: Excel version of the above data.
- **mod_regular_press_conferences.csv**: CSV data containing regular press conference data.
- **mod_regular_press_conferences.jsonl**: JSONL data for regular press conferences.
- **mod_regular_press_conferences.xlsx**: Excel file for regular press conferences.
- **mod_regular_press_transcripts.csv**: CSV file containing transcripts from regular press conferences.
- **mod_regular_press_transcripts.jsonl**: JSONL file with transcripts from regular press conferences.
- **mod_regular_press_transcripts.xlsx**: Excel version of the above.
- **mod_special_press_conferences.csv**: CSV file containing data on special press conferences.
- **mod_special_press_conferences.jsonl**: JSONL version for special press conferences.
- **mod_special_press_conferences.xlsx**: Excel file for special press conferences.
- **mod_spokesperson_remarks_qna.csv**: CSV file with spokesperson remarks and Q&A.
- **mod_spokesperson_remarks_qna.jsonl**: JSONL file with spokesperson remarks and Q&A.
- **mod_spokesperson_remarks_qna.xlsx**: Excel file for spokesperson remarks and Q&A.

#### Trump White House Website:
- **trump_whitehouse_news_data.csv**: CSV file containing press release and news data from the Trump White House.
- **trump_whitehouse_news_data.jsonl**: JSONL version of the data from the Trump White House.
- **trump_whitehouse_news_data.xlsx**: Excel file containing the same data as the CSV file.

#### U.S. Department of State:
- **state_department_press_briefings.csv**: CSV file with press briefing data from the U.S. Department of State.
- **state_department_press_briefings.json**: JSON file with press briefing data.
- **state_department_press_briefings.xlsx**: Excel file with press briefing data.
- **state_department_press_releases_2021_2025.csv**: CSV file containing press releases from the U.S. Department of State from 2021 to 2025.
- **state_department_press_releases_2021_2025.json**: JSON file for press releases from 2021 to 2025.
- **state_department_press_releases_2021_2025.xlsx**: Excel version of the above.
- **state_department_press_releases_2025_update.csv**: CSV file containing updated press releases for 2025.
- **state_department_press_releases_2025_update.json**: JSON file for the 2025 update press releases.
- **state_department_press_releases_2025_update.xlsx**: Excel file for the 2025 update.

### Data Format and Field Descriptions:

#### CSV Files:
Each CSV file contains data in the following columns:

1. **publish_time**: The publication date of the briefing or release.
2. **type**: The type of briefing or release (e.g., regular press briefing, spokesperson remarks).
3. **title**: The title of the briefing or release.
4. **content**: The full content of the briefing or release, which may include questions and answers (Q&A).
5. **source_url**: The URL where the briefing or release is published on the respective official website.

#### JSONL Files:
Each line in the JSONL files represents one record in JSON format with the same fields as the CSV files.

#### XLSX Files:
The XLSX files contain the same data as the CSV files but are formatted for use in Excel.

---

## 中文

此数据集包含来自多个来源的数据，包括 **白宫**、**中国外交部与国防部** 和 **美国国务院**。数据主要由这些机构的新闻简报、新闻发布和声明组成。数据集提供了不同格式（CSV、JSONL 和 XLSX）以便进行不同的数据处理需求。

### 数据集中的文件：

1. **Biden White House Website**: 包含拜登白宫的新闻简报数据，包括新闻发布会和新闻发布。
2. **Ministry of Foreign Affairs of China**: 包含中国外交部的新闻发布会数据。
3. **Ministry of National Defense of China**: 包含中国国防部的新闻发布、新闻发布会和实录。
4. **Trump White House Website**: 包含特朗普白宫的新闻数据，包括新闻发布和新闻简报。
5. **U.S. Department of State**: 包含美国国务院的新闻发布和简报数据，涵盖2021到2025年。

### 数据集字段：

数据集包含以下字段：

1. **publish_time**: 新闻简报或发布的发布时间。
2. **type**: 简报或发布的类型（例如，例行新闻发布会，发言人谈话）。
3. **title**: 简报或发布的标题。
4. **content**: 简报的主要内容或正文，可能包括问答（Q&A）。
5. **source_url**: 简报或发布所在的官方网站链接。

### 文件和用途：

- **CSV 文件**：这些文件包含表格数据，兼容 Excel 或任何支持 CSV 文件的软件，通常用于数据分析。
- **JSONL 文件**：这些文件中的每一行是一个 JSON 对象，表示一个记录，适合编程任务中的数据处理。
- **XLSX 文件**：这些文件是 CSV 文件的 Excel 版本，适合使用 Excel 处理的用户。

### 每个文件的作用：

#### Biden White House Website:
- **biden_briefing_room_data_final.csv**: 包含拜登白宫的新闻简报数据，格式为 CSV。每一行代表一篇新闻简报，包含标题、日期、类型和内容等元数据。
- **biden_briefing_room_data_final.jsonl**: 与 CSV 相同的数据，存储为 JSONL 格式。每行是一个 JSON 对象，代表一篇简报。
- **biden_briefing_room_data_final.xlsx**: 与 CSV 文件相同的数据，以 Excel 格式保存。

#### Ministry of Foreign Affairs of China（一个早期爬虫的备份，可能包含目前网站上已经删除的信息）:
- **国防部_专题记者会.xlsx**: 来自中国国防部的新闻发布会数据，格式为 XLSX。
- **国防部_例行记者会.xlsx**: 来自中国国防部的例行新闻发布会数据。
- **国防部_例行新闻发布会.xlsx**: 来自中国国防部的新闻发布数据。
- **国防部_例行记者会实录.xlsx**: 中国国防部例行新闻发布会的实录。
- **外交部_例行记者会数据.xlsx**: 来自中国外交部的新闻发布会数据。
- **国防部_发言人谈话和答记者问.xlsx**: 来自中国国防部的发言人谈话及问答数据。

#### Ministry of National Defense of China:
- **mod_regular_news_briefings.csv**: 包含中国国防部的定期新闻简报数据（CSV 格式）。
- **mod_regular_news_briefings.jsonl**: JSONL 格式的定期新闻简报数据。
- **mod_regular_news_briefings.xlsx**: Excel 格式的定期新闻简报数据。
- **mod_regular_press_conferences.csv**: 中国国防部的定期新闻发布会数据（CSV 格式）。
- **mod_regular_press_conferences.jsonl**: 定期新闻发布会数据（JSONL 格式）。
- **mod_regular_press_conferences.xlsx**: 定期新闻发布会数据（Excel 格式）。
- **mod_regular_press_transcripts.csv**: 中国国防部的定期新闻发布会实录数据（CSV 格式）。
- **mod_regular_press_transcripts.jsonl**: 实录数据（JSONL 格式）。
- **mod_regular_press_transcripts.xlsx**: 实录数据（Excel 格式）。
- **mod_special_press_conferences.csv**: 中国国防部的专题新闻发布会数据（CSV 格式）。
- **mod_special_press_conferences.jsonl**: 专题新闻发布会数据（JSONL 格式）。
- **mod_special_press_conferences.xlsx**: 专题新闻发布会数据（Excel 格式）。
- **mod_spokesperson_remarks_qna.csv**: 发言人谈话及问答数据（CSV 格式）。
- **mod_spokesperson_remarks_qna.jsonl**: 发言人谈话及问答数据（JSONL 格式）。
- **mod_spokesperson_remarks_qna.xlsx**: 发言人谈话及问答数据（Excel 格式）。

#### Trump White House Website:
- **trump_whitehouse_news_data.csv**: 来自特朗普白宫的新闻数据（CSV 格式）。
- **trump_whitehouse_news_data.jsonl**: 来自特朗普白宫的新闻数据（JSONL 格式）。
- **trump_whitehouse_news_data.xlsx**: 来自特朗普白宫的新闻数据（Excel 格式）。

#### U.S. Department of State:
- **state_department_press_briefings.csv**: 来自美国国务院的新闻简报数据（CSV 格式）。
- **state_department_press_briefings.json**: 来自美国国务院的新闻简报数据（JSON 格式）。
- **state_department_press_briefings.xlsx**: 来自美国国务院的新闻简报数据（Excel 格式）。
- **state_department_press_releases_2021_2025.csv**: 美国国务院2021-2025年间的新闻发布数据（CSV 格式）。
- **state_department_press_releases_2021_2025.json**: 美国国务院2021-2025年间的新闻发布数据（JSON 格式）。
- **state_department_press_releases_2021_2025.xlsx**: 美国国务院2021-2025年间的新闻发布数据（Excel 格式）。
- **state_department_press_releases_2025_update.csv**: 2025年更新的美国国务院新闻发布数据（CSV 格式）。
- **state_department_press_releases_2025_update.json**: 2025年更新的美国国务院新闻发布数据（JSON 格式）。
- **state_department_press_releases_2025_update.xlsx**: 2025年更新的美国国务院新闻发布数据（Excel 格式）。

### 数据格式和字段说明：

#### CSV 文件：
每个 CSV 文件包含以下列：

1. **publish_time**: 新闻简报或发布的发布时间。
2. **type**: 简报或发布的类型（例如，例行新闻发布会，发言人谈话）。
3. **title**: 简报或发布的标题。
4. **content**: 简报的主要内容或正文，可能包括问答（Q&A）。
5. **source_url**: 简报或发布所在的官方网站链接。

#### JSONL 文件：
每行表示一个 JSON 对象，格式与 CSV 相同，适合编程任务中的数据处理。

#### XLSX 文件：
Excel 格式，内容与 CSV 文件相同，适合使用 Excel 处理的用户。

---

This `README.md` file provides a comprehensive overview of the dataset. Feel free to explore and make use of the data according to your needs!
