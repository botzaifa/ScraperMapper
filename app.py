import streamlit as st
import pandas as pd
from io import BytesIO
from bs4 import BeautifulSoup
import re, json

# ------------------- HELPERS -------------------

def _first(*vals):
    for v in vals:
        if isinstance(v, str) and v.strip():
            return v.strip()
    return ""

def _jsonlds(soup):
    data=[]
    for s in soup.select('script[type="application/ld+json"]'):
        try:
            blob=json.loads(s.string)
            if isinstance(blob, list): data.extend(blob)
            else: data.append(blob)
        except Exception:
            continue
    return data

def _get_residence(lds):
    for o in lds:
        if o.get("@type")=="Residence":
            return o
    return None

# ------------------- TEXT SCRAPER -------------------

def extract_bayut_fields(html: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    lds  = _jsonlds(soup)
    res  = _get_residence(lds)

    row = {
        "Property Name*": "",
        "Seller Name*": "",
        "Property Type*": "",
        "Description": "",
        "Location": "",        
        "Country*": "UAE",
        "Bathrooms*": "",
        "Bedrooms*": "",
        "Google Map URL*": "",
        "Latitude": "",
        "Longitude": "",
        "Property Area*": "",
        "Plot Area (sq ft)": "",
        "Total Floors": "",
        "Instant Buy": "",
        "Purchase Price*": "",
        "Down-payment Type": "",
        "Down-payment Value": "",
        "Down-payment Price": "",
        "Service Charge": "",
        "Handover Date (Quarter)": "",
        "Handover Date (Year)": "",
        "Completion Status*": "",
        "Furnishing Status*": "",
        "Year Build": "",
        "Reference Number": "",
        
        # Regulatory
        "Permit Number": "",
        "BRN": "",
        "DED": "",
        "RERA": "",
        "Zone Name": "",
        "Registered Agency": "",
        "ARRA": "",
    }

    # Property Name
    h1 = soup.find("h1")
    if h1:
        row["Property Name*"] = h1.get_text(strip=True)

    # Description
    desc_el = soup.select_one('[aria-label="Property description"]') \
        or soup.find("div", {"data-testid": "listing-description"})
    if desc_el:
        row["Description"] = desc_el.get_text(" ", strip=True)

    # Location
    loc_el = soup.find("div", {"aria-label": "Property header"})
    if loc_el:
        row["Location"] = loc_el.get_text(" ", strip=True)

    # Country from JSON-LD
    if res and isinstance(res.get("address"), dict):
        row["Country*"] = res["address"].get("addressCountry", "UAE")

    # Beds / Baths / Area from JSON-LD (fallbacks)
    if res:
        row["Bedrooms*"] = str((res.get("numberOfRooms") or {}).get("value", "")) or row["Bedrooms*"]
        row["Bathrooms*"] = str(res.get("numberOfBathroomsTotal", "")) or row["Bathrooms*"]
        row["Property Area*"] = str((res.get("floorSize") or {}).get("value", "")) or row["Property Area*"]

    # ---------- SPECIFIC MAPPING FOR Beds / Baths / Area ----------
    def _grab_feature(label_regex: str) -> str:
        el = soup.find("span", {"aria-label": re.compile(label_regex, re.I)})
        if not el:
            return ""
        val_el = el.find("span", class_="_3458a9d4") or el
        return val_el.get_text(" ", strip=True)

    beds  = _grab_feature(r"^Beds$")
    baths = _grab_feature(r"^Baths$")
    area  = _grab_feature(r"^Area$")

    if beds:  row["Bedrooms*"]      = beds        
    if baths: row["Bathrooms*"]     = baths       
    if area:  row["Property Area*"] = area        

    # --- Other specs
    for spec in soup.find_all("span", {"aria-label": True}):
        label = spec["aria-label"].strip().lower()
        inner_val = spec.find("span", class_="_3458a9d4")
        value = (inner_val.get_text(" ", strip=True)
                 if inner_val else spec.get_text(" ", strip=True))

        if "reference" in label:
            row["Reference Number"] = value
        elif "total floors" in label:
            row["Total Floors"] = value
        elif "year of completion" in label:
            row["Year Build"] = value
        elif "handover date" in label:
            val = value.upper()
            if re.match(r"Q\d\s+\d{4}", val):
                q, y = val.split()
                row["Handover Date (Quarter)"] = q
                row["Handover Date (Year)"] = y
            elif re.match(r"\d{4}", val):
                row["Handover Date (Year)"] = val

    # Price
    for o in lds:
        if o.get("@type") == "ItemPage" and isinstance(o.get("mainEntity"), dict):
            offers = o["mainEntity"].get("offers") or []
            if isinstance(offers, list) and offers:
                ps = offers[0].get("priceSpecification", {})
                row["Purchase Price*"] = ps.get("price", "")

    # Property Type
    m = re.search(r'"property_type"\s*:\s*"([^"]+)"', html, re.I)
    if m:
        row["Property Type*"] = m.group(1).rstrip("s").title()

    # Seller Name
    for o in lds:
        if o.get("@type") == "ItemPage":
            me = o.get("mainEntity") or {}
            off = (me.get("offers") or [{}])[0]
            offeredBy = off.get("offeredBy") or {}
            org = offeredBy.get("parentOrganization") or {}
            row["Seller Name*"] = _first(org.get("name",""), offeredBy.get("name",""))

    # Completion Status
    m = re.search(r'"completion_status"\s*:\s*"([^"]+)"', html, re.I)
    if m:
        row["Completion Status*"] = m.group(1).replace("-", " ").title()

    # Instant Buy rule
    if row["Completion Status*"].lower() == "under construction":
        row["Instant Buy"] = ""
    else:
        row["Instant Buy"] = "Yes"

    # Furnishing Status
    furnish_el = soup.find("li", {"aria-label": "Property furnishing status"})
    if furnish_el:
        val = furnish_el.get_text(" ", strip=True)
        if "Furnish" in val:
            val = val.split()[-1]
        row["Furnishing Status*"] = val

    # ✅ Extended Regulatory info
    for li in soup.select("ul._7d2126bd li"):
        label_el = li.find("div", class_="_52bcc5bc")
        value_el = li.find("span", class_="_677f9d24")
        if not label_el or not value_el:
            continue

        label = label_el.get_text(strip=True).lower()
        value = value_el.get_text(strip=True)

        if "permit number" in label:
            row["Permit Number"] = value
        elif "zone name" in label:
            row["Zone Name"] = value
        elif "registered agency" in label:
            row["Registered Agency"] = value
        elif label == "ded":
            row["DED"] = value
        elif label == "rera":
            row["RERA"] = value
        elif label == "arra":
            row["ARRA"] = value
        elif label == "brn":
            row["BRN"] = value

    # Lat/Lon
    if res and isinstance(res.get("geo"), dict):
        row["Latitude"] = str(res["geo"].get("latitude",""))
        row["Longitude"] = str(res["geo"].get("longitude",""))

    if (not row["Latitude"] or not row["Longitude"]) and lds:
        for obj in lds:
            if isinstance(obj, dict) and isinstance(obj.get("geo"), dict):
                row["Latitude"] = str(obj["geo"].get("latitude",""))
                row["Longitude"] = str(obj["geo"].get("longitude",""))
                break

    # Google Maps URL
    if row["Latitude"] and row["Longitude"]:
        row["Google Map URL*"] = f"https://www.google.com/maps?q={row['Latitude']},{row['Longitude']}"

    return row

# ------------------- STREAMLIT APP -------------------

st.title("ScraperMapper")

uploaded_file = st.file_uploader("Upload saved Bayut .txt file", type=["txt","html"])

if uploaded_file:
    html = uploaded_file.read().decode("utf-8", errors="ignore")

    # --- Text fields ---
    fields = extract_bayut_fields(html)
    st.subheader("Extracted Property Fields:")
    st.json(fields)

    df = pd.DataFrame([fields])
    output = BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False)
    output.seek(0)
    st.download_button("⬇️ Download Excel", output, file_name="bayut_property.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


# =========================================================
# 🔽 NEW PIXELBIN + WATERMARK REMOVER SECTION BELOW 🔽
# =========================================================

import io, zipfile, requests, os, time, asyncio, tempfile
from urllib.parse import urlsplit, urlunsplit
from pathlib import Path
from pixelbin import PixelbinClient, PixelbinConfig
from pixelbin.utils.url import url_to_obj, obj_to_url


def init_event_loop():
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(asyncio.sleep(0.1))
init_event_loop()


# ---------------- SCRAPER HELPERS ----------------
def strip_query(u: str) -> str:
    p = urlsplit(u)
    return urlunsplit((p.scheme, p.netloc, p.path, "", ""))

def find_all_image_urls(raw_html: str):
    pattern = re.compile(r'https?://[^\s"\'<>]+?\.(?:jpg|jpeg|webp)(?:\?[^\s"\'<>]*)?', re.IGNORECASE)
    urls = pattern.findall(raw_html)
    normalized, seen = [], set()
    for u in urls:
        clean = strip_query(u)
        if clean not in seen:
            seen.add(clean)
            normalized.append(clean)
    return normalized

def filter_property_images(urls):
    pattern = re.compile(r"-800x600\.webp$", re.I)
    kept = []
    for u in urls:
        host = urlsplit(u).netloc.lower()
        if "bayut" not in host:
            continue
        if pattern.search(u):
            kept.append(u)
    return kept

def extract_gallery_images(raw_html: str):
    all_urls = find_all_image_urls(raw_html)
    property_imgs = filter_property_images(all_urls)
    return sorted(set(property_imgs))


# ---------------- PIXELBIN HELPERS ----------------
def upload_to_pixelbin(url, client):
    r = requests.get(url, stream=True, timeout=20)
    r.raise_for_status()
    fname = Path(urlsplit(url).path).name
    suffix = "." + fname.split(".")[-1]
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(r.content)
        tmp_path = tmp.name
    with open(tmp_path, "rb") as f:
        result = client.uploader.upload(
            file=f,
            name=fname,
            path="",
            format=fname.split(".")[-1],
            access="public-read",
            overwrite=True
        )
    os.remove(tmp_path)
    return result.get("url")

def build_transform_url(asset_url, *, remove_text=True, remove_logo=True, out_format="png"):
    obj = url_to_obj(asset_url)
    transforms, wm_values = [], []
    if remove_text: wm_values.append({"key": "rem_text", "value": "true"})
    if remove_logo: wm_values.append({"key": "rem_logo", "value": "true"})
    if wm_values: transforms.append({"plugin": "wm", "name": "remove", "values": wm_values})
    transforms.append({"plugin": "t", "name": "toFormat", "values": [{"key": "f", "value": out_format}]})
    obj["transformations"] = transforms
    return obj_to_url(obj)

def download_with_poll(url, filename, max_retries=12, wait_seconds=1.0):
    for attempt in range(max_retries):
        r = requests.get(url, stream=True)
        if r.status_code == 202:
            time.sleep(wait_seconds)
            continue
        r.raise_for_status()
        file_bytes = io.BytesIO()
        for chunk in r.iter_content(chunk_size=8192):
            if chunk:
                file_bytes.write(chunk)
        file_bytes.seek(0)
        return filename, file_bytes
    raise RuntimeError("Transformation did not finish in time (kept returning 202).")


# ---------------- STREAMLIT WATERMARK REMOVER ----------------
if uploaded_file:
    raw = html
    gallery = extract_gallery_images(raw)

    st.markdown("---")
    st.header("Property Images:")

    st.caption("Debug:")
    st.write({
        "total_img_like_urls_found_in_html": len(find_all_image_urls(raw)),
        "after_property_filter": len(filter_property_images(find_all_image_urls(raw))),
        "final_gallery_count": len(gallery),
    })

    if gallery:
        cols = st.columns(5)
        for i, url in enumerate(gallery[:10]):
            with cols[i % 5]:
                st.image(url, width=120)

        if st.button("📦 Download All Images as ZIP"):
            buf = io.BytesIO()
            with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
                for i, url in enumerate(gallery, 1):
                    ext = ".webp" if url.lower().endswith(".webp") else ".jpg"
                    fname = f"image_{i:02d}{ext}"
                    try:
                        r = requests.get(url, timeout=20)
                        r.raise_for_status()
                        zf.writestr(fname, r.content)
                    except Exception as e:
                        st.warning(f"Failed: {url} — {e}")
            buf.seek(0)
            st.download_button("⬇️ Download gallery.zip", buf, "gallery.zip", "application/zip")

        st.markdown("---")
        st.subheader("🔑 PixelBin Credentials")
        api_token  = st.text_input("Enter your PixelBin API Token", type="password")
        # access_key = st.text_input("Enter your PixelBin Access Key (optional)", type="password")

        if api_token:
            config = PixelbinConfig({
                "domain": "https://api.pixelbin.io",
                "apiSecret": api_token
            })
            client = PixelbinClient(config=config)

            st.subheader("Watermark Remover (PixelBin)")
            if st.button("✨ Remove All Watermarks"):
                if not gallery:
                    st.error("No valid images found.")
                else:
                    st.success(f"Found {len(gallery)} images. Processing...")
                    processed_files = []
                    progress = st.progress(0)

                    for i, url in enumerate(gallery, 1):
                        with st.spinner(f"Processing image {i}/{len(gallery)}"):
                            try:
                                src_url = upload_to_pixelbin(url, client)
                                transformed_url = build_transform_url(src_url, remove_text=True, remove_logo=True, out_format="png")
                                fname = f"cleaned_{i:02d}.png"
                                fname, file_bytes = download_with_poll(transformed_url, fname)
                                processed_files.append((fname, file_bytes))
                            except Exception as e:
                                st.warning(f"Failed {url}: {e}")
                        progress.progress(i / len(gallery))

                    if processed_files:
                        st.markdown("### 🖼️ Cleaned Previews")
                        cols = st.columns(4)
                        for i, (fname, file_bytes) in enumerate(processed_files, 1):
                            with cols[(i - 1) % 4]:
                                st.image(file_bytes, width=150, caption=f"#{i}")

                        zip_buffer = io.BytesIO()
                        with zipfile.ZipFile(zip_buffer, "w") as zipf:
                            for filename, file_bytes in processed_files:
                                zipf.writestr(filename, file_bytes.getvalue())
                        zip_buffer.seek(0)

                        st.download_button("📦 Download Cleaned ZIP", zip_buffer, "cleaned_gallery.zip", "application/zip")
        else:
            st.info("⚠️ Please enter your PixelBin API Token above to enable watermark removal.")
    else:
        st.error("No property images detected. Ensure you copied the FULL outerHTML of the listing page.")
