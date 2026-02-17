# Centro Clínico Santiago — MVP (Streamlit)

Streamlit MVP for reception intake + billing review (HITL) + basic analytics.

## Run locally
```bash
python -m streamlit run app.py


---

## 4) Commit and push (so Streamlit Cloud can deploy)

In Terminal (inside the MVP folder):

```bash
cd /Users/vue/Desktop/MVP
git status
git add requirements.txt .gitignore README.md
git commit -m "Add deployment files for Streamlit Cloud"
git push origin main
