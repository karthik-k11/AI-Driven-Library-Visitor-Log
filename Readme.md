# 📚 AI-Driven Library Visitor Log  

An AI-powered system that automates student registration in libraries using **OCR (Optical Character Recognition)** and **SQLite database**. The project eliminates the need for manual visitor logbooks by extracting details directly from student ID cards.  

---

## 🚀 Features  
- 📷 **Camera-based OCR**: Capture ID card details in real time.  
- 📝 **Automatic Field Extraction**: Extracts **Name, Registration Number, Department** from ID cards.  
- 🗄 **SQLite Database Integration**: Stores visitor details securely.  
- 🖥 **Flask Web Dashboard**: View recent visitors in a clean web interface.  
- 🔍 **Validation & Duplicate Check**: Ensures only valid and unique records are stored.  

---

## 📊 Project Workflow  

### **Use Case 1 – Basic Model**  
1. Capture student ID card image (via webcam).  
2. Apply OCR (`pytesseract`) to extract text.  
3. Extract **Name, ID Number, Department** using regex & keyword-based logic.  
4. Validate and check duplicates.  
5. Store in SQLite database (`library_visitors.db`).  
6. Display registered visitors on the dashboard.  

### **Use Case 2 – Advanced Model (Future Scope)**  
- Live photo capture & face matching.  
- QR code scanning for fast check-in.  
- Admin dashboard with analytics.  

---

## 🛠 Tech Stack  

- **Python** 🐍  
- **Flask** – Web framework  
- **SQLite** – Local database  
- **OpenCV** – Camera input & image preprocessing  
- **Pytesseract** – OCR engine  
- **Pandas** – Data handling  
- **HTML + CSS (Jinja2)** – Web templates  

---

## 🎯 Scope  
- Provides a **low-cost, automated solution** for maintaining digital visitor records.  
- Saves time for librarians and reduces manual entry errors.  
- Can be extended with **face recognition, QR scanning, and analytics**.  

---

## ⚠️ Limitations  
- OCR accuracy depends on ID card quality & lighting.  
- Currently supports **specific ID formats** (college-based).  
- Advanced features like **face recognition** are not yet implemented.  

---