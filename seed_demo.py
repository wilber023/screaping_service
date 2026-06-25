"""
Siembra productos de demostración para todos los 14 cultivos.
Correr en EC2:  docker-compose exec api python seed_demo.py
"""
import os, sys, hashlib, uuid
from datetime import datetime

# Asegura que toma DATABASE_URL del entorno (ya está seteado en el contenedor)
sys.path.insert(0, "/app")

from scraping.storage.database import SessionLocal, engine
from scraping.models.base import Base
from scraping.models.product import Product

Base.metadata.create_all(bind=engine)

def h(*parts):
    return hashlib.sha256("|".join(parts).lower().encode()).hexdigest()

def p(source, url, name, manufacturer, ingredient, tipo, crops, diseases, price, currency="MXN", regions=None, stock=50):
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
    }

PRODUCTOS = [
    # ── TOMATE ────────────────────────────────────────────────────────────────
    p("syngenta","https://www.syngenta.com.mx/productos/amistar-top",
      "Amistar Top 325 SC","Syngenta","Azoxistrobina 200 g/L + Difenoconazol 125 g/L",
      "fungicida",["tomate","papa","uva","fresa"],
      ["tizón tardío","alternaria","botrytis","oidio"],1250),

    p("bayer","https://www.cropscience.bayer.mx/productos/previcur-energy",
      "Previcur Energy","Bayer","Fosetil aluminio 310 g/L + Propamocarb 530 g/L",
      "fungicida",["tomate","papa","calabaza","pimiento"],
      ["tizón tardío","mildiu","damping-off"],890),

    p("syngenta","https://www.syngenta.com.mx/productos/actara",
      "Actara 25 WG","Syngenta","Tiametoxam 250 g/kg",
      "insecticida",["tomate","papa","naranja","uva","fresa"],
      ["mosca blanca","áfidos","trips","escama"],780),

    p("basf","https://agriculture.basf.com/mx/es/productos/cabrio-duo.html",
      "Cabrio Duo","BASF","Piraclostrobina 133 g/L + Metiram 467 g/L",
      "fungicida",["tomate","papa","maiz","uva"],
      ["tizón tardío","alternaria","antracnosis"],1100),

    p("bayer","https://www.cropscience.bayer.mx/productos/confidor",
      "Confidor 350 SC","Bayer","Imidacloprid 350 g/L",
      "insecticida",["tomate","papa","calabaza","pimiento"],
      ["mosca blanca","áfidos","minador de hoja"],650),

    p("syngenta","https://www.syngenta.com.mx/productos/ridomil-gold",
      "Ridomil Gold MZ 68 WP","Syngenta","Metalaxil-M 4% + Mancozeb 64%",
      "fungicida",["tomate","papa","pimienta","uva"],
      ["tizón tardío","mildiu","Phytophthora"],720),

    # ── MAÍZ ──────────────────────────────────────────────────────────────────
    p("syngenta","https://www.syngenta.com.mx/productos/karate-zeon",
      "Karate Zeon 250 CS","Syngenta","Lambda-cialotrina 250 g/L",
      "insecticida",["maiz","tomate","papa","frijol","soja"],
      ["gusano cogollero","trips","mosca blanca","áfidos"],620),

    p("basf","https://agriculture.basf.com/mx/es/productos/headline.html",
      "Headline 250 EC","BASF","Piraclostrobina 250 g/L",
      "fungicida",["maiz","soja","frijol"],
      ["roya común","tizón foliar","antracnosis"],980),

    p("agrofy","https://www.agrofy.com.ar/agroquimicos/herbicidas/glifosato-48",
      "Glifosato 48% SL","AgroFlex","Glifosato sal isopropilamina 480 g/L",
      "herbicida",["maiz","soja","frijol","trigo"],
      ["malezas de hoja ancha","gramíneas anuales","coquillo"],280,regions=["MX","AR"]),

    p("syngenta","https://www.syngenta.com.mx/productos/lumax",
      "Lumax 537.5 SE","Syngenta","S-Metolacloro 312.5 g/L + Atrazina 187.5 g/L + Mesotriona 37.5 g/L",
      "herbicida",["maiz"],
      ["zacate Johnson","quelite","correhuela","verdolaga"],540),

    p("bayer","https://www.cropscience.bayer.mx/productos/decis",
      "Decis 2.5 CE","Bayer","Deltametrina 25 g/L",
      "insecticida",["maiz","papa","frijol","soja"],
      ["gusano cogollero","diabrótica","pulgón"],380),

    # ── PAPA ──────────────────────────────────────────────────────────────────
    p("bayer","https://www.cropscience.bayer.mx/productos/infinito",
      "Infinito 687.5 SC","Bayer","Fluopicolide 62.5 g/L + Propamocarb 625 g/L",
      "fungicida",["papa","tomate"],
      ["tizón tardío","Phytophthora infestans"],1380),

    p("syngenta","https://www.syngenta.com.mx/productos/engeo",
      "Engeo 247 ZC","Syngenta","Lambda-cialotrina 106 g/L + Tiametoxam 141 g/L",
      "insecticida",["papa","maiz","frijol","soja"],
      ["diabrótica","áfidos","chicharrita","thrips"],850),

    p("basf","https://agriculture.basf.com/mx/es/productos/bellis.html",
      "Bellis 38 WG","BASF","Piraclostrobina 12.8% + Boskalida 25.2%",
      "fungicida",["papa","fresa","uva","manzana"],
      ["tizón temprano","alternaria","botrytis","oidio"],1450),

    # ── FRIJOL ────────────────────────────────────────────────────────────────
    p("bayer","https://www.cropscience.bayer.mx/productos/topsin",
      "Topsin M 70 WP","Bayer","Tiofanato metílico 700 g/kg",
      "fungicida",["frijol","maiz","soja","tomate"],
      ["antracnosis","mancha foliar","Botrytis"],420),

    p("syngenta","https://www.syngenta.com.mx/productos/score",
      "Score 250 EC","Syngenta","Difenoconazol 250 g/L",
      "fungicida",["frijol","manzana","cebolla","zanahoria"],
      ["roya","antracnosis","alternaria","cenicilla"],590),

    p("basf","https://agriculture.basf.com/mx/es/productos/basagran.html",
      "Basagran 600 SL","BASF","Bentazona 600 g/L",
      "herbicida",["frijol","soja","maiz"],
      ["chufa","verdolaga","quelite","coquillo"],460),

    # ── FRESA ─────────────────────────────────────────────────────────────────
    p("syngenta","https://www.syngenta.com.mx/productos/switch",
      "Switch 62.5 WG","Syngenta","Ciprodinil 37.5% + Fludioxonil 25%",
      "fungicida",["fresa","uva","mora","frambuesa","cereza"],
      ["botrytis","monilia","podredumbre del fruto"],1180),

    p("bayer","https://www.cropscience.bayer.mx/productos/movento",
      "Movento 150 OD","Bayer","Spirotetramat 150 g/L",
      "insecticida",["fresa","uva","mora","frambuesa","durazno","manzana"],
      ["trips","mosca blanca","áfidos","cochinilla"],1320),

    p("basf","https://agriculture.basf.com/mx/es/productos/luna-sensation.html",
      "Luna Sensation 500 SC","BASF","Fluopyram 250 g/L + Trifloxistrobina 250 g/L",
      "fungicida",["fresa","uva","manzana","cereza","durazno"],
      ["botrytis","oidio","alternaria","monilia"],1560),

    # ── UVA ───────────────────────────────────────────────────────────────────
    p("bayer","https://www.cropscience.bayer.mx/productos/aliette",
      "Aliette 80 WP","Bayer","Fosetil aluminio 800 g/kg",
      "fungicida",["uva","naranja","aguacate","frambuesa"],
      ["mildiu","Plasmopara viticola","Phytophthora"],580),

    p("syngenta","https://www.syngenta.com.mx/productos/curzate",
      "Curzate M 72 WP","Syngenta","Cimoxanil 8% + Mancozeb 64%",
      "fungicida",["uva","tomate","papa","pimienta"],
      ["mildiu","tizón tardío","Plasmopara"],490),

    p("basf","https://agriculture.basf.com/mx/es/productos/poliram.html",
      "Poliram 700 DF","BASF","Metiram 700 g/kg",
      "fungicida",["uva","manzana","pera","tomate"],
      ["mildiu","alternaria","sarna del manzano"],380),

    # ── MANZANA ───────────────────────────────────────────────────────────────
    p("bayer","https://www.cropscience.bayer.mx/productos/manzate",
      "Manzate 200 DF","Bayer","Mancozeb 800 g/kg",
      "fungicida",["manzana","pera","uva","papa","tomate"],
      ["sarna del manzano","alternaria","mildiu"],310),

    p("bayer","https://www.cropscience.bayer.mx/productos/calypso",
      "Calypso 480 SC","Bayer","Thiacloprid 480 g/L",
      "insecticida",["manzana","cereza","durazno","pera"],
      ["pulgón verde","psila del manzano","trips"],890),

    p("syngenta","https://www.syngenta.com.mx/productos/chorus",
      "Chorus 75 WG","Syngenta","Ciprodinil 750 g/kg",
      "fungicida",["manzana","cereza","durazno","pera","uva"],
      ["sarna del manzano","monilia","podredumbre"],1050),

    # ── DURAZNO / CEREZA / MORA / FRAMBUESA ───────────────────────────────────
    p("bayer","https://www.cropscience.bayer.mx/productos/indar",
      "Indar 75 WSB","Bayer","Fenbuconazol 750 g/kg",
      "fungicida",["durazno","cereza","ciruela","chabacano"],
      ["monilia","tiro de munición","cloca"],980),

    p("bayer","https://www.cropscience.bayer.mx/productos/teldor",
      "Teldor 500 SC","Bayer","Fenhexamida 500 g/L",
      "fungicida",["cereza","fresa","uva","mora","frambuesa"],
      ["botrytis","monilia","podredumbre gris"],1240),

    p("basf","https://agriculture.basf.com/mx/es/productos/scala.html",
      "Scala 400 SC","BASF","Pirimetanil 400 g/L",
      "fungicida",["mora","frambuesa","fresa","uva","manzana"],
      ["botrytis","alternaria","monilia"],1080),

    # ── SOJA ──────────────────────────────────────────────────────────────────
    p("basf","https://agriculture.basf.com/mx/es/productos/priori-xtra.html",
      "Priori Xtra 280 SC","BASF","Azoxistrobina 200 g/L + Ciproconazol 80 g/L",
      "fungicida",["soja","maiz","frijol"],
      ["roya asiática","mancha ojo de rana","antracnosis"],920),

    p("syngenta","https://www.syngenta.com.mx/productos/gramoxone",
      "Gramoxone 200 SL","Syngenta","Paraquat dicloruro 200 g/L",
      "herbicida",["soja","maiz","frijol","caña de azúcar"],
      ["malezas anuales","gramíneas","hoja ancha"],295),

    # ── CALABAZA ──────────────────────────────────────────────────────────────
    p("bayer","https://www.cropscience.bayer.mx/productos/confidor-maxx",
      "Confidor Maxx 70 WG","Bayer","Imidacloprid 700 g/kg",
      "insecticida",["calabaza","pepino","melón","sandía"],
      ["mosca blanca","áfidos","minador de hoja","trips"],720),

    p("syngenta","https://www.syngenta.com.mx/productos/ortiva",
      "Ortiva 250 SC","Syngenta","Azoxistrobina 250 g/L",
      "fungicida",["calabaza","pepino","melón","tomate","papa"],
      ["cenicilla","alternaria","antracnosis","tizón"],880),

    # ── NARANJA ───────────────────────────────────────────────────────────────
    p("bayer","https://www.cropscience.bayer.mx/productos/derosal",
      "Derosal 500 SC","Bayer","Carbendazim 500 g/L",
      "fungicida",["naranja","limón","toronja","mandarina"],
      ["gomosis","antracnosis","melanosis"],440),

    p("syngenta","https://www.syngenta.com.mx/productos/vertimec",
      "Vertimec 18 EC","Syngenta","Abamectina 18 g/L",
      "insecticida",["naranja","limón","aguacate","mango"],
      ["ácaro rojo","minador de la hoja","trips"],780),

    # ── PIMIENTA ──────────────────────────────────────────────────────────────
    p("basf","https://agriculture.basf.com/mx/es/productos/signum.html",
      "Signum 33 WG","BASF","Piraclostrobina 6.7% + Boskalida 26.7%",
      "fungicida",["pimienta","tomate","papa","fresa"],
      ["botrytis","alternaria","cenicilla","antracnosis"],1190),

    p("bayer","https://www.cropscience.bayer.mx/productos/oberon",
      "Oberon 240 SC","Bayer","Spiromesifen 240 g/L",
      "insecticida",["pimienta","tomate","pepino","fresa"],
      ["mosca blanca","ácaro blanco","trips"],950),

    # ── PAPA extra ────────────────────────────────────────────────────────────
    p("mercadolibre","https://www.mercadolibre.com.mx/mancozeb",
      "Mancozeb 80% WP Genérico","AgriQuím","Mancozeb 800 g/kg",
      "fungicida",["papa","tomate","cebolla","ajo"],
      ["tizón temprano","tizón tardío","alternaria"],185),

    # ── FERTILIZANTES UNIVERSALES ─────────────────────────────────────────────
    p("syngenta","https://www.syngenta.com.mx/productos/kristalon",
      "Kristalon Rojo 18-18-18","Syngenta","N 18% + P2O5 18% + K2O 18% + microelementos",
      "fertilizante",["tomate","papa","maiz","frijol","fresa","uva","calabaza","pimienta"],
      ["deficiencia nutricional","clorosis","enanismo"],680),

    p("basf","https://agriculture.basf.com/mx/es/productos/haifa.html",
      "Nitrato de Potasio 13-0-46","Haifa","N 13% + K2O 46%",
      "fertilizante",["tomate","papa","fresa","pimienta","pepino","uva"],
      ["deficiencia de potasio","maduración deficiente"],520),
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
        print("Listo. Recarga el HTML para ver los productos.")
    finally:
        db.close()


if __name__ == "__main__":
    main()