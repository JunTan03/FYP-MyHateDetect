
# MyHateDetect – Multilingual Hate Speech Detection System

MyHateDetect is a dual-stage classification platform for detecting and categorising **hate speech** in English and Malay texts. Built with a focus on code-switched social media texts (tweets), the system uses multilingual BERT (mBERT) to ensure high accuracy across diverse linguistic contexts.

## Research & Publication

The binary classification model (Stage 1) and the underlying dataset used in this project have been formally published:

* **Research Paper:** [A bilingual Malay-English social media dataset for binary hate speech detection](https://doi.org/10.1016/j.dib.2025.112153) (Published in *Data in Brief, ScienceDirect*).
* **Official Dataset:** [A Bilingual Malay-English Social Media Dataset for Binary Hate Speech Detection](https://data.mendeley.com/datasets/mgv2n2vcb9/3) (Hosted on *Mendeley Data*).

## System Architecture

**Stage 1: binary classification (hate vs non-hate):** Determine if a tweet contains hate speech. 

**Stage 2: multilabel hate type classification:** Identify the specific nature of the hate speech (Race, Religion, Gender, Sexual Orientation).

## Performance

The system is fine-tuned over 10,000 bilingual tweets. mBERT is selected for deployment due to its performances in both stages.

**Stage 1**
Shows high True Positive counts, effectively filtering toxic content.
![Stage 1 Confusion Matrix](./experiment/stage1/s1_mb_confusion_matrix.png)


**Stage 2**
Reveals how different categories, such as Race and Religion, often overlap in toxic discourse.
![Stage 2 Label Co-occurences](./experiment/stage2/s2_mb_label_cooccurrence.png)

## Features

* **Dual-Stage Pipeline:** Optimised detection architecture. Stage 1 acts as a filter (Hate vs. Non-Hate), while Stage 2 performs deep-dive categorisation.
* **Multilingual BERT (mBERT) Integration:** Specifically fine-tuned for high accuracy in both English and Malay, outperforming standard monolingual models.
* **Role-Based Access Control (RBAC):** Secure access for **Admins** (system management and CSV uploads) and **Policymakers** (read-only visualisation and trend analysis).
* **Zero-Config NLP:** Automated NLTK resource setup on first launch.

## Folder Structure

```
MyHateDetect/
├── app/
│   ├── templates/            # HTML for dashboard, visualisation, auth
│   ├── routes/               # Flask Blueprints
│   ├── static/               # Logo used in UI
│   ├── stage_predict.py      # Final prediction script (stage 1 + 2)
│   ├── text_utils.py         # Preprocessing & Auto-NLTK setup
│   └── utils.py              # Progress bar, database functions
├── sql query/
│   └── myhatedetect.sql      # MySQL database dump
├── experiment/
│   ├── stage1/               # Binary classification: Training notebooks, model weights & performance visuals
│   ├── stage2/               # Multi-label classification: Training notebooks, model weights & visuals
├── sample_uploads   # Sample dataset files for tweets upload and user registration use
├── requirements.txt          # Clean list of dependencies for website
├── run.py                    # Entry point for Flask app
└── README.md                 # Project documentation and setup guide
```

## Installation & Setup

**1. Clone the Repository**
```bash
git clone https://github.com/JunTan03/FYP-MyHateDetect.git
cd MyHateDetect
```
**2. Install Dependencies**
```bash
pip install -r requirements.txt
```
**3. Database Setup**
* Ensure MySQL is running amd import the database dump
```bash
mysql -u root -p myhatedetect < sql query/myhatedetect.sql
```
**4. Run the Application**
```bash
python run.py
```
Visit: [http://localhost:5000](http://localhost:5000)

## Demo Credentials

| Role        | Email                   | Password    |
|-------------|-------------------------|--------------
| Admin       | jtan4148@gmail.com      | 12345678    |
| Policymaker | (Create via Admin)      |             |

## Upload Rules for Tweet

- Column must be `text` or `tweet`
- Duplicate `file_name` and `month` will be skipped
- All inputs cleaned and language-detected

## License
This project is licensed under the MIT License - see the [LICENSE](./LICENSE) file for details.