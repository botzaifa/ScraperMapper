
# 🏠 ScraperMapper

> Extract structured property data and watermark-free images from Bayut listings — all in your browser.

**ScraperMapper** is a browser-based real estate data extractor and image cleaner built with [Streamlit](https://streamlit.io), [BeautifulSoup](https://www.crummy.com/software/BeautifulSoup/), and [PixelBin](https://pixelbin.io). It transforms raw Bayut listing HTML into Excel-friendly data and clean ZIPs of gallery images — ideal for real estate agents, analysts, and property data platforms.

[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://scrapermapper.streamlit.app)
[![Made with Streamlit](https://img.shields.io/badge/Built%20with-Streamlit-FF4B4B?logo=streamlit&logoColor=white)](https://streamlit.io)
[![Uses PixelBin API](https://img.shields.io/badge/Image%20Cleaning-PixelBin-blue)](https://pixelbin.io)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## 🌐 Live Demo

👉 **Launch the App:** [scrapermapper.streamlit.app](https://scrapermapper.streamlit.app)

---

## 🔍 What It Does

- 📄 Extracts 30+ property fields (beds, baths, price, furnishing, agency, regulatory info, etc.)
- 🖼️ Detects and downloads full image gallery
- 🧼 Removes text & logo watermarks using PixelBin API
- 📊 Exports data as **Excel**
- 📦 Downloads all images (original & cleaned) as ZIP
- ✅ Fully browser-based – **no scraping bots or browser automation**

---

## 📥 Input Format

Upload the **saved HTML or TXT file** of a Bayut listing.

> 💡 Use “Save As → Webpage, HTML only” or right-click and “Inspect → Copy Outer HTML” from your browser.

---

## 📤 Output Format

1. **Excel (`.xlsx`)** with structured fields
2. **ZIP archive** of gallery images (original + cleaned)

---

## 🧠 Extracted Fields

- Property Name, Seller, Type, Description
- Beds, Baths, Area, Furnishing
- Price, Location, Latitude/Longitude, Google Map URL
- Completion Status, Handover Date, Year Built
- Regulatory Fields (Permit, RERA, DED, BRN, etc.)

> Uses both structured JSON-LD metadata and DOM parsing for maximum accuracy.

---

## ✨ Watermark Removal with PixelBin

To clean watermarks:

1. Sign up at [PixelBin.io](https://pixelbin.io)
2. Create an API Token from your dashboard
3. Paste your token into the app
4. Hit **“✨ Remove All Watermarks”** and download the ZIP

🎨 Cleaned images are returned as `.png` with both **text and logo** removed.

---

## 🧰 How to Run Locally

### 1. Clone the Repository

```bash
git clone https://github.com/botzaifa/ScraperMapper.git
cd ScraperMapper
````

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Launch the Streamlit App

```bash
streamlit run app.py
```

---

## 🛠️ Built With

| Tool              | Purpose                      |
| ----------------- | ---------------------------- |
| Streamlit         | Web app interface            |
| BeautifulSoup     | HTML parsing & DOM selection |
| PixelBin API      | Watermark removal            |
| Pandas/XlsxWriter | Data export to Excel         |
| Requests          | File/image handling          |

---

## 🖼️ Sample Output (Excel + Images)

| Field          | Value                           |
| -------------- | ------------------------------- |
| Property Name  | Luxury 2BR in Dubai Hills       |
| Bedrooms       | 2                               |
| Bathrooms      | 2                               |
| Location       | Dubai Hills Estate              |
| Furnishing     | Furnished                       |
| Purchase Price | 1,900,000 AED                   |
| Google Maps    | [Open](https://maps.google.com) |

> Preview thumbnails of both **original** and **cleaned images** are shown in the app before download.

---


## 🔗 Useful Links

* 📂 GitHub Repo: [ScraperMapper](https://github.com/botzaifa/ScraperMapper)
* 🧼 PixelBin API: [pixelbin.io](https://pixelbin.io)
* 🏘️ Bayut Website: [bayut.com](https://www.bayut.com)

---

## 🙋 FAQ

**Q: Can I use this without coding knowledge?**
Yes! Just visit the [Streamlit App](https://scrapermapper.streamlit.app) — no setup needed.

**Q: Will this work on other real estate sites?**
Currently, it’s tailored for **Bayut.com** listings only.

**Q: Is there a limit to image cleaning?**
PixelBin’s free tier has usage limits. Heavy use may require a paid plan.

---

## 💬 Feedback & Contributions

If you find a bug or have a feature request, open an [issue](https://github.com/botzaifa/ScraperMapper/issues) or submit a pull request.

---

Thanks ~Huzaifa 👷‍♂️
