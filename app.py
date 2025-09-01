import streamlit as st
import pandas as pd
from io import BytesIO
from bs4 import BeautifulSoup
import re, json, io, zipfile, requests, os, time, asyncio, tempfile
from urllib.parse import urlsplit, urlunsplit
from pathlib import Path
from pixelbin import PixelbinClient, PixelbinConfig
from pixelbin.utils.url import url_to_obj, obj_to_url

# =========================================================
# COMMON HELPERS
# =========================================================

def init_event_loop():
    """
    Ensure there is an event loop for async calls when running inside Streamlit.
    This avoids "There is no current event loop in thread 'ScriptRunner.scriptThread'".
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        # run a tiny no-op so the loop is usable
        loop.run_until_complete(asyncio.sleep(0.01))

init_event_loop()

def strip_query(u: str) -> str:
    p = urlsplit(u)
    return urlunsplit((p.scheme, p.netloc, p.path, "", ""))

def find_all_image_urls(raw_html: str):
    """
    Find common image URLs (jpg/jpeg/webp) in HTML text (very permissive).
    """
    pattern = re.compile(r'https?://[^\s"\'<>]+?\.(?:jpg|jpeg|webp)(?:\?[^\s"\'<>]*)?', re.IGNORECASE)
    urls = pattern.findall(raw_html or "")
    normalized, seen = [], set()
    for u in urls:
        clean = strip_query(u)
        if clean not in seen:
            seen.add(clean)
            normalized.append(clean)
    return normalized

def _first(*vals):
    """Return first non-empty string-like value."""
    for v in vals:
        if isinstance(v, str) and v.strip():
            return v.strip()
    return ""

def _jsonlds(soup: BeautifulSoup):
    """Parse all application/ld+json blocks and return list of parsed objects."""
    out = []
    for s in soup.find_all("script", {"type": "application/ld+json"}):
        try:
            if not s.string:
                continue
            data = json.loads(s.string)
            # some pages return a single dict or a list
            if isinstance(data, list):
                out.extend(data)
            else:
                out.append(data)
        except Exception:
            # try to recover some malformed JSON by stripping whitespace/newlines
            try:
                data = json.loads(s.string.strip())
                if isinstance(data, list):
                    out.extend(data)
                else:
                    out.append(data)
            except Exception:
                continue
    return out

def _get_residence(lds):
    """Try to pick a residence-like JSON-LD entry (fallback to first dict)."""
    if not lds:
        return {}
    for o in lds:
        t = o.get("@type") if isinstance(o, dict) else None
        if t and any(k in str(t).lower() for k in ("residence", "apartment", "house", "product", "offer")):
            return o
    # fallback: return first dict-like item
    for o in lds:
        if isinstance(o, dict):
            return o
    return {}

def upload_to_pixelbin(client, url):
    """Upload remote URL to PixelBin using a temporary file and return the uploaded URL."""
    r = requests.get(url, stream=True, timeout=20)
    r.raise_for_status()
    fname = Path(urlsplit(url).path).name or f"image_{int(time.time())}.jpg"
    suffix = "." + fname.split(".")[-1] if "." in fname else ".jpg"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(r.content)
        tmp_path = tmp.name
    try:
        with open(tmp_path, "rb") as f:
            # usage may differ depending on pixelbin SDK version; this is a common pattern
            result = client.uploader.upload(
                file=f,
                name=fname,
                path="",
                format=fname.split(".")[-1],
                access="public-read",
                overwrite=True
            )
    finally:
        try:
            os.remove(tmp_path)
        except Exception:
            pass
    # result may contain 'url' or 'data' depending on SDK; be defensive:
    if isinstance(result, dict):
        return result.get("url") or result.get("data", {}).get("url") or result.get("data", {}).get("originalUrl")
    return None

def build_transform_url(asset_url, *, remove_text=True, remove_logo=True, out_format="png"):
    """Create a PixelBin-style transform URL from an asset object."""
    obj = url_to_obj(asset_url)
    transforms, wm_values = [], []
    if remove_text: wm_values.append({"key": "rem_text", "value": "true"})
    if remove_logo: wm_values.append({"key": "rem_logo", "value": "true"})
    if wm_values:
        transforms.append({"plugin": "wm", "name": "remove", "values": wm_values})
    transforms.append({"plugin": "t", "name": "toFormat", "values": [{"key": "f", "value": out_format}]})
    obj["transformations"] = transforms
    return obj_to_url(obj)

def download_with_poll(url, filename, max_retries=12, wait_seconds=1.0):
    """
    Poll the transform URL until it's ready (non-202) then download and return (filename, BytesIO).
    """
    for attempt in range(max_retries):
        r = requests.get(url, stream=True, timeout=30)
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

# =========================================================
# BAYUT SCRAPER (from file 2)
# =========================================================

def extract_bayut_fields(html: str) -> dict:
    soup = BeautifulSoup(html or "", "html.parser")
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
        # safety: some schemas store numbers differently
        try:
            row["Bedrooms*"] = str((res.get("numberOfRooms") or {}).get("value", "")) or row["Bedrooms*"]
        except Exception:
            row["Bedrooms*"] = row["Bedrooms*"]
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

    # Price (from JSON-LD offers)
    for o in lds:
        if isinstance(o, dict) and o.get("@type") == "ItemPage" and isinstance(o.get("mainEntity"), dict):
            offers = o["mainEntity"].get("offers") or []
            if isinstance(offers, list) and offers:
                ps = offers[0].get("priceSpecification", {}) or offers[0]
                row["Purchase Price*"] = ps.get("price", "") or ps.get("priceCurrency", "") or row["Purchase Price*"]

    # Property Type (regex fallback)
    m = re.search(r'"property_type"\s*:\s*"([^"]+)"', html or "", re.I)
    if m:
        row["Property Type*"] = m.group(1).rstrip("s").title()

    # Seller Name (from offers.offeredBy)
    for o in lds:
        if isinstance(o, dict) and o.get("@type") == "ItemPage":
            me = o.get("mainEntity") or {}
            off = (me.get("offers") or [{}])[0]
            offeredBy = off.get("offeredBy") or {}
            org = offeredBy.get("parentOrganization") or {}
            row["Seller Name*"] = _first(org.get("name",""), offeredBy.get("name",""), row["Seller Name*"])

    # Completion Status
    m = re.search(r'"completion_status"\s*:\s*"([^"]+)"', html or "", re.I)
    if m:
        row["Completion Status*"] = m.group(1).replace("-", " ").title()

    # Instant Buy rule
    if row["Completion Status*"] and row["Completion Status*"].lower() == "under construction":
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

    # ✅ Extended Regulatory info (resilient selectors)
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

    # Lat/Lon from JSON-LD
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

def extract_gallery_images_bayut(raw_html: str):
    all_urls = find_all_image_urls(raw_html)
    return sorted(set(filter_property_images(all_urls)))

# =========================================================
# PROPERTYFINDER SCRAPER (from file 1)
# =========================================================

def extract_propertyfinder_fields(html: str) -> dict:
    soup = BeautifulSoup(html or "", "html.parser")

    row = {
        "Property Name*": "",
        "Seller Name*": "",
        "Developer Name": "",
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
        "Trakheesi Permit": "",
    }

    # ---------------- PROPERTY NAME ----------------
    desc_div = soup.find("div", id="description")
    if desc_div:
        h1 = desc_div.find("h1", class_="styles_desktop_title__j0uNx") or desc_div.find("h1")
        if h1:
            row["Property Name*"] = h1.get_text(strip=True)

    # ---------------- SELLER NAME (Agent) ----------------
    agent_el = soup.select_one('p[data-testid="property-detail-agent-name"]')
    if agent_el:
        row["Seller Name*"] = agent_el.get_text(strip=True)

    # ---------------- DESCRIPTION ----------------
    if desc_div:
        article = desc_div.select_one('div[data-testid="description-section"] article[data-testid="dynamic-sanitize-html"]')
        if article:
            text = article.get_text("\n", strip=True)
            lines = [line.strip() for line in text.splitlines()]
            text_clean = "\n".join([ln for ln in lines if ln])
            row["Description"] = text_clean

    # ---------------- PROPERTY TYPE ----------------
    type_el = soup.select_one('p[data-testid="property-details-type"]')
    if type_el:
        row["Property Type*"] = type_el.get_text(strip=True)

    # ---------------- PROPERTY AREA ----------------
    area_el = soup.select_one('p[data-testid="property-details-size"]')
    if area_el:
        row["Property Area*"] = area_el.get_text(strip=True)

    # ---------------- BEDROOMS ----------------
    bed_el = soup.select_one('p[data-testid="property-details-bedrooms"]')
    if bed_el:
        row["Bedrooms*"] = bed_el.get_text(strip=True)

    # ---------------- BATHROOMS ----------------
    bath_el = soup.select_one('p[data-testid="property-details-bathrooms"]')
    if bath_el:
        row["Bathrooms*"] = bath_el.get_text(strip=True)

    # ---------------- PURCHASE PRICE ----------------
    price_el = soup.select_one('span[data-testid="property-price-value"]')
    if price_el:
        row["Purchase Price*"] = "AED " + price_el.get_text(strip=True)

    # ---------------- JSON-LD (LAT/LON + LOCATION) ----------------
    script_tag = soup.find("script", {"id": "plp-schema", "type": "application/ld+json"})
    if script_tag and script_tag.string:
        try:
            data = json.loads(script_tag.string)
            main_entity = data.get("mainEntity", {}).get("mainEntity", {}) if isinstance(data, dict) else {}
            # GEO
            geo = (main_entity or {}).get("geo", {}) or data.get("geo", {})
            if geo:
                row["Latitude"] = str(geo.get("latitude", ""))
                row["Longitude"] = str(geo.get("longitude", ""))
                if row["Latitude"] and row["Longitude"]:
                    row["Google Map URL*"] = f"https://www.google.com/maps?q={row['Latitude']},{row['Longitude']}"
            # LOCATION
            address = (main_entity or {}).get("address", {}) or data.get("address", {})
            if isinstance(address, dict):
                row["Location"] = address.get("name", "") or address.get("streetAddress", "") or row["Location"]
        except Exception as e:
            # don't crash the app on JSON parse errors
            print("Error parsing JSON-LD:", e)

    # ---------------- REGULATORY INFO ----------------
    regulatory_div = soup.find("div", class_="styles_desktop_content__Z_YaU")
    if regulatory_div:
        # Reference Number
        ref_el = regulatory_div.select_one('p[data-testid="property-regulatory-reference"]')
        if ref_el:
            row["Reference Number"] = ref_el.get_text(strip=True)

        # Collect all regulatory value <p>
        license_texts = regulatory_div.find_all("p", class_="styles_desktop_value__mxst1")
        for txt_el in license_texts:
            txt = txt_el.get_text(strip=True)
            if ("L.L.C" in txt or "LLC" in txt or "REAL ESTATE" in txt.upper()) and not row["Registered Agency"]:
                row["Registered Agency"] = txt
            elif txt.isdigit() and not row["DED"]:
                row["DED"] = txt

        # Permit Number
        permit_el = regulatory_div.select_one('p[data-testid="property-regulatory-agent-license-no"]')
        if permit_el:
            row["Permit Number"] = permit_el.get_text(strip=True)

        # BRN fallback
        all_vals = [el.get_text(strip=True) for el in license_texts]
        if all_vals:
            for v in reversed(all_vals):
                if v.isdigit():
                    row["BRN"] = v
                    break

        # Zone Name
        zone_label = regulatory_div.find(lambda tag: tag.name == "p" and "Zone name" in tag.get_text())
        if zone_label:
            next_val = zone_label.find_next_sibling("p", class_="styles_desktop_value__mxst1")
            if next_val:
                row["Zone Name"] = next_val.get_text(strip=True)

    # ---------------- TRAKHEESI PERMIT (QR link) ----------------
    qr_div = soup.find("div", {"data-testid": "property-regulatory-qr-code"})
    if qr_div:
        link = qr_div.find("a", href=True)
        if link:
            row["Trakheesi Permit"] = link["href"]

    # ---------------- DEVELOPER NAME ----------------
    if row.get("Registered Agency"):
        row["Developer Name"] = row.get("Registered Agency")
    else:
        broker_name_container = soup.find("div", class_="styles_desktop_broker__name__container__Rnz1J")
        if broker_name_container:
            link = broker_name_container.find("a", href=True)
            if link:
                href = link["href"]
                m = re.search(r'/broker/([^/]+)', href)
                if m:
                    slug = m.group(1)
                    slug = re.sub(r'-\d+$', '', slug)
                    row["Developer Name"] = slug.replace('-', ' ').title()

    return row

def filter_propertyfinder_images(urls):
    kept = []
    pattern = re.compile(r"/(\d{2,4})/(\d{2,4})/MODE/", re.I)
    for u in urls:
        host = urlsplit(u).netloc.lower()
        if "propertyfinder.ae" not in host:
            continue
        m = pattern.search(u)
        if not m:
            continue
        try:
            w, h = int(m.group(1)), int(m.group(2))
        except Exception:
            continue
        if w >= 200 and h >= 200:
            kept.append(u)
    return kept

def pick_highest_resolution(urls):
    key_re = re.compile(r"(.*/\d+)/(\d+)/MODE/([^/]+)/([^/]+)\.(jpg|jpeg|webp)$", re.I)
    buckets, leftovers = {}, []
    for u in urls:
        m = key_re.match(u)
        if not m:
            leftovers.append(u)
            continue
        key = m.group(4)
        try:
            w = int(m.group(2))
            h = int(m.group(3)) if m.group(3).isdigit() else 0
        except Exception:
            w, h = 0, 0
        area = w * h
        best = buckets.get(key)
        if not best or area > best[0]:
            buckets[key] = (area, u)
    best_urls = [t[1] for t in buckets.values()]
    return sorted(set(best_urls + leftovers))

def extract_gallery_images_propertyfinder(raw_html: str):
    return pick_highest_resolution(filter_propertyfinder_images(find_all_image_urls(raw_html)))

# =========================================================
# STREAMLIT APP (updated watermark processing)
# =========================================================

st.title("ScraperMapper")

platform = st.sidebar.radio("Choose Platform", ["Bayut", "PropertyFinder"])

def watermark_ui_and_process(gallery):
    """
    UI for PixelBin settings and processing. Returns list of processed metadata dicts.
    """
    st.markdown("### PixelBin Watermark Remover:")
    api_token = st.text_input("PixelBin API Token (paste here)", type="password")
    col1, col2, col3 = st.columns([1,1,1])
    with col1:
        remove_text = st.checkbox("Remove text watermark", value=True, key="rm_text")
    with col2:
        remove_logo = st.checkbox("Remove logo watermark", value=True, key="rm_logo")
    with col3:
        out_format = st.selectbox("Output format", ["png", "jpg", "webp"], index=0, key="out_fmt")

    # Initialize stop flag in session state
    if "stop_processing" not in st.session_state:
        st.session_state.stop_processing = False

    # Buttons
    colA, colB = st.columns([1,1])
    with colA:
        process_clicked = st.button("▶️ Process watermarks")
    with colB:
        stop_clicked = st.button("⏹ Cancel Processing")

    if stop_clicked:
        st.session_state.stop_processing = True

    processed_meta = []

    if process_clicked:
        if not api_token:
            st.error("PixelBin API token is required to process images.")
            return []

        # Reset stop flag before starting
        st.session_state.stop_processing = False

        # init pixelbin client
        config = PixelbinConfig({
            "domain": "https://api.pixelbin.io",
            "apiSecret": api_token
        })
        client = PixelbinClient(config=config)

        if not gallery:
            st.warning("No gallery images to process.")
            return []

        zip_buffer = BytesIO()
        with zipfile.ZipFile(zip_buffer, "w") as zf:
            for i, url in enumerate(gallery, start=1):
                if st.session_state.stop_processing:
                    st.warning("⏹ Processing stopped by user.")
                    break

                with st.spinner(f"Processing {i}/{len(gallery)}..."):
                    try:
                        # 1) upload original (so transforms work on a PixelBin asset)
                        uploaded_url = upload_to_pixelbin(client, url)
                        if not uploaded_url:
                            raise RuntimeError("Upload to PixelBin failed (no URL returned).")

                        # 2) build transform url
                        transformed_url = build_transform_url(
                            uploaded_url,
                            remove_text=remove_text,
                            remove_logo=remove_logo,
                            out_format=out_format
                        )

                        # 3) poll & download transformed image
                        fname = f"cleaned_{i}.{out_format}"
                        _, file_bytes = download_with_poll(transformed_url, fname)
                        img_bytes = file_bytes.getvalue()

                        # 4) show image + download button
                        st.image(img_bytes, caption=fname, width="stretch")
                        st.download_button(
                            label=f"⬇️ Download {fname}",
                            data=io.BytesIO(img_bytes).getvalue(),
                            file_name=fname,
                            mime=f"image/{out_format}"
                        )

                        # 5) add to zip
                        zf.writestr(fname, img_bytes)

                        processed_meta.append({
                            "index": i,
                            "original_url": url,
                            "uploaded_url": uploaded_url,
                            "transformed_url": transformed_url,
                            "filename": fname,
                            "status": "ok"
                        })
                    except Exception as e:
                        st.error(f"❌ Failed to process image {url}: {e}")
                        processed_meta.append({
                            "index": i,
                            "original_url": url,
                            "uploaded_url": None,
                            "transformed_url": None,
                            "filename": None,
                            "status": f"error: {e}"
                        })

        # make ZIP available if at least one OK file added
        if any(p.get("status") == "ok" for p in processed_meta):
            zip_buffer.seek(0)
            st.download_button(
                label="📥 Download All Images (ZIP)",
                data=zip_buffer.getvalue(),
                file_name="processed_images.zip",
                mime="application/zip"
            )

    return processed_meta


if platform == "Bayut":
    uploaded = st.file_uploader("Upload Bayut HTML (.txt / .html)", type=["txt","html"])
    if uploaded:
        raw = uploaded.read().decode("utf-8", errors="ignore")
        fields = extract_bayut_fields(raw)
        st.subheader("Extracted Property Fields")
        st.json(fields)

        df = pd.DataFrame([fields])
        output = BytesIO()
        with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
            df.to_excel(writer, index=False)
        output.seek(0)
        st.download_button(
            label="⬇️ Download Excel",
            data=output.getvalue(),
            file_name="bayut_property.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

        # Gallery extraction (unchanged)
        gallery = extract_gallery_images_bayut(raw)
        st.subheader(f"Gallery images found: {len(gallery)}")
        if gallery:
            st.image(gallery[:5], width=120)

        # ---------- Watermark processing ----------
        watermark_meta = watermark_ui_and_process(gallery)


elif platform == "PropertyFinder":
    uploaded = st.file_uploader("Upload PropertyFinder HTML (.txt / .html)", type=["txt","html"])
    if uploaded:
        raw = uploaded.read().decode("utf-8", errors="ignore")
        fields = extract_propertyfinder_fields(raw)
        st.subheader("Extracted Property Fields")
        st.json(fields)

        df = pd.DataFrame([fields])
        output = BytesIO()
        with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
            df.to_excel(writer, index=False)
        output.seek(0)
        st.download_button(
            label="⬇️ Download Excel",
            data=output.getvalue(),
            file_name="propertyfinder_property.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

        # Gallery extraction (unchanged)
        gallery = extract_gallery_images_propertyfinder(raw)
        st.subheader(f"Gallery images found: {len(gallery)}")
        if gallery:
            st.image(gallery[:5], width=120)

        # ---------- Watermark processing ----------
        watermark_meta = watermark_ui_and_process(gallery)
