# ScraperMapper

A powerful, browser-based tool to extract structured property data and clean images from **Bayut** listing pages. Built with **Streamlit**, **BeautifulSoup**, and **PixelBin**, ScraperMapper helps real estate professionals easily generate Excel-ready data and watermark-free images from raw listing HTML.

[![Made with Streamlit](https://img.shields.io/badge/Made%20with-Streamlit-FF4B4B?logo=streamlit)](https://streamlit.io)
[![PixelBin API](https://img.shields.io/badge/Uses%20PixelBin%20API-%F0%9F%94%91-blue)](https://pixelbin.io/)


---

## 📌 Features

- ✅ Extracts structured data from Bayut property listings
- ✅ Automatically detects and downloads gallery images
- ✅ Removes **text and logo watermarks** using PixelBin API
- ✅ Exports all data to **Excel**
- ✅ Bulk-download **cleaned images** as ZIP
- ✅ No browser automation required

---

## 📁 Input

Upload a **saved `.html` or `.txt` file** (outerHTML) of a Bayut property page.

---

## 📦 Installation

Clone the repo:

```bash
git clone https://github.com/botzaifa/ScraperMapper.git
cd ScraperMapper
````

Install dependencies:

```bash
pip install -r requirements.txt
```

---

## 🚀 Run the App

```bash
streamlit run app.py
```

This will launch a browser window where you can interact with the tool.

---

## ✨ PixelBin Integration (Watermark Remover)

To use the watermark remover, you'll need an API token from [PixelBin.io](https://pixelbin.io).

1. Sign up at [pixelbin.io](https://pixelbin.io)
2. Generate an API token from your dashboard
3. Paste it into the app when prompted
4. Hit **"✨ Remove All Watermarks"** to clean all gallery images

---

## 🧾 Output

* **Excel File (`.xlsx`)** with extracted fields
* **ZIP File** containing original and cleaned gallery images

---

## 🖼️ Example

| Field             | Value                                     |
| ----------------- | ----------------------------------------- |
| Property Name     | Elegant 2BR in Downtown                   |
| Bathrooms         | 2                                         |
| Bedrooms          | 2                                         |
| Location          | Downtown Dubai                            |
| Furnishing Status | Furnished                                 |
| Purchase Price    | 1,800,000 AED                             |
| Google Map URL    | [Link](https://www.google.com/maps?q=...) |

---

## 🧠 How It Works

* Parses **JSON-LD**, **aria-labels**, and embedded metadata
* Extracts data like beds, baths, area, furnishing, price, etc.
* Finds and filters **Bayut property images**
* Uses **PixelBin’s watermark removal API** to clean images

---

## 🛠️ Tech Stack

* [Streamlit](https://streamlit.io)
* [BeautifulSoup](https://www.crummy.com/software/BeautifulSoup/)
* [PixelBin API](https://docs.pixelbin.io/)
* [XlsxWriter](https://xlsxwriter.readthedocs.io/)

---

## 🔒 License

MIT License © [botzaifa](https://github.com/botzaifa)

---

## 🌐 Links

* 🔗 GitHub Repo: [ScraperMapper](https://github.com/botzaifa/ScraperMapper)
* 🖼️ PixelBin: [https://pixelbin.io](https://pixelbin.io)
* 📄 Bayut: [https://www.bayut.com](https://www.bayut.com)

```

---

