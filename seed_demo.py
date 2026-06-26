"""
Siembra productos de demostración para los 7 cultivos objetivo.
Correr en EC2:  docker-compose exec api python seed_demo.py
"""
import os, sys, hashlib, uuid
from datetime import datetime

sys.path.insert(0, "/app")

from scraping.storage.database import SessionLocal, engine
from scraping.models.base import Base
from scraping.models.product import Product

Base.metadata.create_all(bind=engine)

def h(*parts):
    return hashlib.sha256("|".join(parts).lower().encode()).hexdigest()

_IMG = {
    "fungicida":    "https://images.unsplash.com/photo-1416879595882-3373a0480b5b?w=400&q=80",
    "insecticida":  "https://images.unsplash.com/photo-1559813114-cef6a57cb72f?w=400&q=80",
    "herbicida":    "https://images.unsplash.com/photo-1464226184884-fa280b87c399?w=400&q=80",
    "fertilizante": "https://images.unsplash.com/photo-1591086430580-b4e2ceae6e91?w=400&q=80",
    "otro":         "https://images.unsplash.com/photo-1416879595882-3373a0480b5b?w=400&q=80",
}

def p(source, url, name, manufacturer, ingredient, tipo, crops, diseases, price, currency="MXN", regions=None, stock=50, img=None):
    return {
        "id": str(uuid.uuid4()),
        "source": source,
        "source_url": url,
        "name": name,
        "manufacturer": manufacturer,
        "active_ingredient": ingredient,
        "product_type": tipo,
        "target_crops": crops,
        "target_diseases": diseases,
        "price_amount": price,
        "price_currency": currency,
        "price_original_currency": currency,
        "price_last_updated": datetime.utcnow(),
        "stock_status": "in_stock",
        "stock_quantity": stock,
        "availability_regions": regions or ["MX"],
        "scraped_at": datetime.utcnow(),
        "hash_dedup": h(source, name, ingredient),
        "is_active": True,
        "image_url": img or _IMG.get(tipo, _IMG["fungicida"]),
    }

PRODUCTOS = [
    # ── TOMATE ────────────────────────────────────────────────────────────────
    p("syngenta","https://www.syngenta.com.mx/productos/amistar-top",
      "Amistar Top 325 SC","Syngenta","Azoxistrobina 200 g/L + Difenoconazol 125 g/L",
      "fungicida",["tomate","papa","fresa"],
      ["tizón tardío","alternaria","botrytis","oidio"],1250),

    p("bayer","https://www.cropscience.bayer.mx/productos/previcur-energy",
      "Previcur Energy","Bayer","Fosetil aluminio 310 g/L + Propamocarb 530 g/L",
      "fungicida",["tomate","papa","calabaza"],
      ["tizón tardío","mildiu","damping-off"],890),

    p("syngenta","https://www.syngenta.com.mx/productos/actara",
      "Actara 25 WG","Syngenta","Tiametoxam 250 g/kg",
      "insecticida",["tomate","papa","fresa"],
      ["mosca blanca","áfidos","trips","escama"],780),

    p("basf","https://agriculture.basf.com/mx/es/productos/cabrio-duo.html",
      "Cabrio Duo","BASF","Piraclostrobina 133 g/L + Metiram 467 g/L",
      "fungicida",["tomate","papa","maiz"],
      ["tizón tardío","alternaria","antracnosis"],1100),

    p("bayer","https://www.cropscience.bayer.mx/productos/confidor",
      "Confidor 350 SC","Bayer","Imidacloprid 350 g/L",
      "insecticida",["tomate","papa","calabaza"],
      ["mosca blanca","áfidos","minador de hoja"],650),

    p("syngenta","https://www.syngenta.com.mx/productos/ridomil-gold",
      "Ridomil Gold MZ 68 WP","Syngenta","Metalaxil-M 4% + Mancozeb 64%",
      "fungicida",["tomate","papa"],
      ["tizón tardío","mildiu","Phytophthora"],720),

    # ── MAÍZ ──────────────────────────────────────────────────────────────────
    p("syngenta","https://www.syngenta.com.mx/productos/karate-zeon",
      "Karate Zeon 250 CS","Syngenta","Lambda-cialotrina 250 g/L",
      "insecticida",["maiz","tomate","papa","frijol"],
      ["gusano cogollero","trips","mosca blanca","áfidos"],620),

    p("basf","https://agriculture.basf.com/mx/es/productos/headline.html",
      "Headline 250 EC","BASF","Piraclostrobina 250 g/L",
      "fungicida",["maiz","frijol"],
      ["roya común","tizón foliar","antracnosis"],980),

    p("agrofy","https://www.agrofy.com.ar/agroquimicos/herbicidas/glifosato-48",
      "Glifosato 48% SL","AgroFlex","Glifosato sal isopropilamina 480 g/L",
      "herbicida",["maiz","frijol"],
      ["malezas de hoja ancha","gramíneas anuales","coquillo"],280,regions=["MX","AR"]),

    p("syngenta","https://www.syngenta.com.mx/productos/lumax",
      "Lumax 537.5 SE","Syngenta","S-Metolacloro 312.5 g/L + Atrazina 187.5 g/L + Mesotriona 37.5 g/L",
      "herbicida",["maiz"],
      ["zacate Johnson","quelite","correhuela","verdolaga"],540),

    p("bayer","https://www.cropscience.bayer.mx/productos/decis",
      "Decis 2.5 CE","Bayer","Deltametrina 25 g/L",
      "insecticida",["maiz","papa","frijol"],
      ["gusano cogollero","diabrótica","pulgón"],380),

    # ── PAPA ──────────────────────────────────────────────────────────────────
    p("bayer","https://www.cropscience.bayer.mx/productos/infinito",
      "Infinito 687.5 SC","Bayer","Fluopicolide 62.5 g/L + Propamocarb 625 g/L",
      "fungicida",["papa","tomate"],
      ["tizón tardío","Phytophthora infestans"],1380),

    p("syngenta","https://www.syngenta.com.mx/productos/engeo",
      "Engeo 247 ZC","Syngenta","Lambda-cialotrina 106 g/L + Tiametoxam 141 g/L",
      "insecticida",["papa","maiz","frijol"],
      ["diabrótica","áfidos","chicharrita","thrips"],850),

    p("basf","https://agriculture.basf.com/mx/es/productos/bellis.html",
      "Bellis 38 WG","BASF","Piraclostrobina 12.8% + Boskalida 25.2%",
      "fungicida",["papa","fresa"],
      ["tizón temprano","alternaria","botrytis","oidio"],1450),

    p("mercadolibre","https://www.mercadolibre.com.mx/mancozeb",
      "Mancozeb 80% WP Genérico","AgriQuím","Mancozeb 800 g/kg",
      "fungicida",["papa","tomate"],
      ["tizón temprano","tizón tardío","alternaria"],185),

    # ── FRIJOL ────────────────────────────────────────────────────────────────
    p("bayer","https://www.cropscience.bayer.mx/productos/topsin",
      "Topsin M 70 WP","Bayer","Tiofanato metílico 700 g/kg",
      "fungicida",["frijol","maiz","tomate"],
      ["antracnosis","mancha foliar","Botrytis"],420),

    p("syngenta","https://www.syngenta.com.mx/productos/score",
      "Score 250 EC","Syngenta","Difenoconazol 250 g/L",
      "fungicida",["frijol","tomate","papa"],
      ["roya","antracnosis","alternaria","cenicilla"],590),

    p("basf","https://agriculture.basf.com/mx/es/productos/basagran.html",
      "Basagran 600 SL","BASF","Bentazona 600 g/L",
      "herbicida",["frijol","maiz"],
      ["chufa","verdolaga","quelite","coquillo"],460),

    # ── FRESA ─────────────────────────────────────────────────────────────────
    p("syngenta","https://www.syngenta.com.mx/productos/switch",
      "Switch 62.5 WG","Syngenta","Ciprodinil 37.5% + Fludioxonil 25%",
      "fungicida",["fresa","mora"],
      ["botrytis","monilia","podredumbre del fruto"],1180),

    p("bayer","https://www.cropscience.bayer.mx/productos/movento",
      "Movento 150 OD","Bayer","Spirotetramat 150 g/L",
      "insecticida",["fresa","mora"],
      ["trips","mosca blanca","áfidos","cochinilla"],1320),

    p("basf","https://agriculture.basf.com/mx/es/productos/luna-sensation.html",
      "Luna Sensation 500 SC","BASF","Fluopyram 250 g/L + Trifloxistrobina 250 g/L",
      "fungicida",["fresa","mora","tomate"],
      ["botrytis","oidio","alternaria","monilia"],1560),

    p("basf","https://agriculture.basf.com/mx/es/productos/signum.html",
      "Signum 33 WG","BASF","Piraclostrobina 6.7% + Boskalida 26.7%",
      "fungicida",["fresa","tomate","papa"],
      ["botrytis","alternaria","cenicilla","antracnosis"],1190),

    p("bayer","https://www.cropscience.bayer.mx/productos/oberon",
      "Oberon 240 SC","Bayer","Spiromesifen 240 g/L",
      "insecticida",["fresa","tomate","calabaza"],
      ["mosca blanca","ácaro blanco","trips"],950),

    # ── MORA ──────────────────────────────────────────────────────────────────
    p("bayer","https://www.cropscience.bayer.mx/productos/teldor",
      "Teldor 500 SC","Bayer","Fenhexamida 500 g/L",
      "fungicida",["mora","fresa"],
      ["botrytis","monilia","podredumbre gris"],1240),

    p("basf","https://agriculture.basf.com/mx/es/productos/scala.html",
      "Scala 400 SC","BASF","Pirimetanil 400 g/L",
      "fungicida",["mora","fresa"],
      ["botrytis","alternaria","monilia"],1080),

    p("syngenta","https://www.syngenta.com.mx/productos/chorus",
      "Chorus 75 WG","Syngenta","Ciprodinil 750 g/kg",
      "fungicida",["mora","fresa","tomate"],
      ["botrytis","monilia","podredumbre"],1050),

    # ── CALABAZA ──────────────────────────────────────────────────────────────
    p("bayer","https://www.cropscience.bayer.mx/productos/confidor-maxx",
      "Confidor Maxx 70 WG","Bayer","Imidacloprid 700 g/kg",
      "insecticida",["calabaza","tomate"],
      ["mosca blanca","áfidos","minador de hoja","trips"],720),

    p("syngenta","https://www.syngenta.com.mx/productos/ortiva",
      "Ortiva 250 SC","Syngenta","Azoxistrobina 250 g/L",
      "fungicida",["calabaza","tomate","papa"],
      ["cenicilla","alternaria","antracnosis","tizón"],880),

    p("basf","https://agriculture.basf.com/mx/es/productos/priori-xtra.html",
      "Priori Xtra 280 SC","BASF","Azoxistrobina 200 g/L + Ciproconazol 80 g/L",
      "fungicida",["calabaza","maiz","frijol"],
      ["cenicilla","roya","antracnosis"],920),

    # ── FERTILIZANTES ─────────────────────────────────────────────────────────
    p("syngenta","https://www.syngenta.com.mx/productos/kristalon",
      "Kristalon Rojo 18-18-18","Syngenta","N 18% + P2O5 18% + K2O 18% + microelementos",
      "fertilizante",["tomate","papa","maiz","frijol","fresa","calabaza"],
      ["deficiencia nutricional","clorosis","enanismo"],680),

    p("basf","https://agriculture.basf.com/mx/es/productos/haifa.html",
      "Nitrato de Potasio 13-0-46","Haifa","N 13% + K2O 46%",
      "fertilizante",["tomate","papa","fresa","mora","calabaza"],
      ["deficiencia de potasio","maduración deficiente"],520),

    p("bayer","https://www.cropscience.bayer.mx/productos/wuxal",
      "Wuxal Boro","Bayer","Nitrógeno 8% + Boro 9%",
      "fertilizante",["frijol","maiz","tomate","calabaza"],
      ["deficiencia de boro","aborto floral"],390),
]


def main():
    db = SessionLocal()
    try:
        existing = db.query(Product).count()
        print(f"Productos actuales en BD: {existing}")

        inserted = 0
        skipped = 0
        for data in PRODUCTOS:
            exists = db.query(Product).filter(
                Product.hash_dedup == data["hash_dedup"]
            ).first()
            if exists:
                skipped += 1
                continue
            db.add(Product(**data))
            inserted += 1

        db.commit()
        total = db.query(Product).count()
        print(f"Insertados: {inserted} | Ya existían: {skipped} | Total BD: {total}")
        print("Listo. Los 7 cultivos: calabaza, frijol, mora, maíz, papa, fresa, tomate.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
