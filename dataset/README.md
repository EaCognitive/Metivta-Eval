# Dataset Directory Documentation

This directory contains datasets and resources for the Metivta Eval benchmarking platform.

## 🚀 Quick Start for Users

### Step 1: View Available Questions
```bash
make show-questions
```
This displays all 27 evaluation questions and offers to export a template.

### Step 2: Fill in Your Answers
Replace `<<<YOUR ANSWER HERE>>>` placeholders in the template with your answers:
```json
{
    "outputs": {
        "answer": "The source is found in Divrei Yoel on Parashat Beha'alotcha where it discusses נצוצות קדושות. See https://tashma.co.il/source/link"
    }
}
```

### Step 3: Validate Your Submission
```bash
make validate-submission FILE=dataset/my-answers.json
```

### Step 4: Submit for Evaluation
Your answers will be scored on:
- 📊 **Basic Requirements**: Hebrew text, URLs, sufficient length (>100 chars)
- 📚 **Scholarly Standards**: Torah citation format, academic tone
- ✅ **Correctness**: Accuracy compared to ground truth
- 🌐 **Source Validation**: Working URLs with relevant content

## 📁 Dataset Files

### Primary Evaluation Datasets

#### Q1-dataset.json (PRIVATE - DO NOT SHARE)
- **Purpose:** Ground truth dataset with questions and expert-validated answers
- **Security:** Must remain private to prevent benchmark gaming
- **Contents:** 27 scholarly Torah Q&A pairs with Hebrew text and citations

#### full_QA_set.json  
- **Purpose:** Complete dataset used by LangSmith evaluation pipeline
- **Format:** LangSmith-compatible format with inputs/outputs structure

#### Q1-questions-only.json
- **Purpose:** Public questions without answers for user submissions
- **Contents:** Same 27 questions as Q1-dataset but without answers

### User Testing Files

#### test-user-submissions.json
- **Purpose:** Template file for users to fill in their answers
- **Format:** Questions with `[ENTER YOUR ANSWER HERE]` placeholders

#### test_small.json
- **Purpose:** Small subset for quick testing and development
- **Contents:** 2-3 Q&A pairs from main dataset

### Evaluation Rubrics

#### maturity_rubric.json
- **Purpose:** Defines scoring criteria for format and structure evaluation
- **Contents:** JSON schema defining expected format standards

### Additional Datasets

#### torah_qa_dataset.json
- **Purpose:** General Torah knowledge questions for supplementary testing
- **Note:** Not part of core benchmarking suite, preserved for future use

## 💡 Tips for High Scores

1. **Include Hebrew Text**: Quote original sources in Hebrew
2. **Cite Real URLs**: Use actual links to Torah databases
3. **Be Detailed**: Answers should be thorough (>100 chars minimum)
4. **Follow Conventions**: Use standard Torah citation format
5. **Multiple Sources**: Having multiple URLs doesn't hurt (we take the best)

### Example High-Scoring Answer
```json
{
    "answer": "The concept of נצוצות קדושות connected to personal possessions appears in דברי יואל, פרשת בהעלותך, where the Satmar Rebbe explains that כל אדם יש לו מחלקי הקדושה נצוצות קדושות השייכים לשורשו. Every item a person owns contains holy sparks specific to their soul's root that await elevation through proper use. See https://tashma.co.il/books/learn/19079/דברי_יואל_על_התורה/במדבר/פרשת_בהעלותך/כה?line=57"
}
```

## 🔒 Security Notes

⚠️ **IMPORTANT:** Files containing ground truth answers (Q1-dataset.json, full_QA_set.json) must never be committed to public repositories or shared with users being evaluated. These are already excluded in .gitignore.

## 📊 File Relationships

```
Q1-dataset.json (source) 
    ↓
full_QA_set.json (LangSmith format)
    ↓
Q1-questions-only.json (public questions)
    ↓
test-user-submissions.json (user template)
```

## 📈 Statistics
- **Total Questions:** 27
- **Dataset Version:** Q1
- **Last Updated:** 09/12/2025