# AgroGrap — Integración del Servicio de Recomendación de Productos

## Estado actual

| Módulo | Estado |
|---|---|
| Frontend móvil → LLM (diagnóstico) | ✅ Funcionando |
| LLM → Frontend (enfermedad detectada) | ✅ Funcionando |
| Frontend → Servicio de productos | ⏳ Pendiente de integrar |
| Servicio de productos → Frontend (cards) | ⏳ Pendiente de integrar |

---

## Servicio

**Host:** `44.196.107.153`  
**Puerto:** `80`  
**Protocolo:** HTTP

---

## Autenticación

**Todas las peticiones requieren este header:**

```http
X-API-Key: {API_KEY}
```

> La `API_KEY` la proporciona el equipo backend. Sin este header la respuesta será `401 Unauthorized`.

---

## Endpoint de Recomendación

```
POST http://44.196.107.153/products/recommend
```

### Headers requeridos

```http
Content-Type: application/json
X-API-Key: {API_KEY}
```

### Body

```json
{
  "disease": "Mildiu",
  "crop": "Tomate"
}
```

| Campo | Tipo | Requerido | Descripción |
|---|---|---|---|
| `disease` | string | ✅ | Enfermedad o plaga detectada por el LLM |
| `crop` | string | ❌ | Cultivo afectado. Mejora la relevancia de resultados |

---

## Respuesta exitosa — `200 OK`

```json
{
  "success": true,
  "disease": "Mildiu",
  "crop": "Tomate",
  "product_type": "fungicida",
  "products": [
    {
      "name": "Fungicida Mancozeb 80 WP 1kg",
      "brand": "AgroMex",
      "description": "mancozeb",
      "image": "https://images-amazon.com/images/I/XXXX.jpg",
      "price": "$420.00 MXN",
      "purchase_url": "https://www.amazon.com.mx/dp/B0XXXXX"
    },
    {
      "name": "Consist Max Tebuconazol + Trifloxistrobina",
      "brand": null,
      "description": "tebuconazol",
      "image": "https://images-amazon.com/images/I/YYYY.jpg",
      "price": "$775.00 MXN",
      "purchase_url": "https://www.amazon.com.mx/dp/B0YYYYY"
    }
  ]
}
```

### Campos de la respuesta raíz

| Campo | Tipo | Descripción |
|---|---|---|
| `success` | boolean | `true` siempre que el servidor procesó la petición |
| `disease` | string | Enfermedad enviada en el request (eco) |
| `crop` | string \| null | Cultivo enviado en el request (eco) |
| `product_type` | string \| null | Tipo inferido: `fungicida`, `insecticida`, `herbicida`, `fertilizante` |
| `products` | array | Lista de productos. Puede ser `[]` si no hay coincidencias |

### Campos de cada producto

| Campo | Tipo | Puede ser null | Descripción |
|---|---|---|---|
| `name` | string | No | Nombre comercial del producto |
| `brand` | string | **Sí** | Marca/fabricante. Verificar antes de mostrar |
| `description` | string | **Sí** | Ingrediente activo. Puede venir vacío |
| `image` | string | **Sí** | URL de imagen del producto. Puede venir null |
| `price` | string | No | Precio en MXN con formato `"$420.00 MXN"` o `"Precio no disponible"` |
| `purchase_url` | string | **Sí** | Link de compra (Amazon u otro marketplace) |

> **Importante:** `brand`, `description`, `image` y `purchase_url` pueden ser `null`. El código debe manejarlo sin romper la UI.

---

## Enfermedades/plagas reconocidas

El servicio infiere el tipo de producto automáticamente según la enfermedad. Ejemplos:

| Enfermedad enviada | Tipo de producto devuelto |
|---|---|
| Mildiu, Botrytis, Tizón, Oidio, Roya, Antracnosis | fungicida |
| Mosca blanca, Trips, Pulgón, Araña roja, Gusano cogollero | insecticida |
| Maleza, Coquillo, Zacate | herbicida |
| Deficiencia nutricional, Clorosis | fertilizante |

Si la enfermedad no coincide con ninguna conocida, el servicio busca por texto en la base de datos.

---

## Implementación en React Native

### Función para obtener recomendaciones

```javascript
const API_URL = "http://44.196.107.153";
const API_KEY = "TU_API_KEY_AQUI"; // Guardar en variables de entorno

const getRecommendedProducts = async (disease, crop) => {
  try {
    const response = await fetch(`${API_URL}/products/recommend`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-API-Key": API_KEY,           // ← obligatorio
      },
      body: JSON.stringify({ disease, crop }),
      signal: AbortSignal.timeout(8000), // timeout 8 segundos
    });

    if (!response.ok) {
      console.error("Error del servicio:", response.status);
      return [];
    }

    const data = await response.json();
    return data.products || [];

  } catch (error) {
    if (error.name === "TimeoutError") {
      console.error("Timeout al cargar productos");
    } else {
      console.error("Error al cargar productos:", error);
    }
    return [];
  }
};
```

### Uso después del diagnóstico

```javascript
// Ejemplo: pantalla de diagnóstico
const DiagnosisScreen = ({ diagnosisResult, selectedCrop }) => {
  const [products, setProducts] = useState([]);
  const [loadingProducts, setLoadingProducts] = useState(false);

  useEffect(() => {
    if (!diagnosisResult?.disease) return;

    // Cargar productos en paralelo — NO bloquear el diagnóstico
    setLoadingProducts(true);
    getRecommendedProducts(diagnosisResult.disease, selectedCrop)
      .then(setProducts)
      .finally(() => setLoadingProducts(false));

  }, [diagnosisResult]);

  return (
    <ScrollView>
      {/* 1. Diagnóstico — se muestra inmediatamente */}
      <DiagnosisCard diagnosis={diagnosisResult} />

      {/* 2. Productos — se cargan en paralelo */}
      <Text style={styles.sectionTitle}>Productos Recomendados</Text>

      {loadingProducts && <ProductSkeleton />}

      {!loadingProducts && products.length === 0 && (
        <Text>No se encontraron productos recomendados.</Text>
      )}

      {products.map((product, index) => (
        <ProductCard key={index} product={product} />
      ))}
    </ScrollView>
  );
};
```

### Componente ProductCard

```javascript
const ProductCard = ({ product }) => {
  const handlePress = () => {
    if (product.purchase_url) {
      Linking.openURL(product.purchase_url);
    }
  };

  return (
    <View style={styles.card}>
      {/* Imagen — puede ser null */}
      {product.image ? (
        <Image
          source={{ uri: product.image }}
          style={styles.productImage}
          defaultSource={require("./assets/product-placeholder.png")}
        />
      ) : (
        <View style={styles.imagePlaceholder} />
      )}

      <View style={styles.info}>
        <Text style={styles.name}>{product.name}</Text>

        {/* Marca — puede ser null */}
        {product.brand && (
          <Text style={styles.brand}>{product.brand}</Text>
        )}

        {/* Ingrediente activo — puede ser null */}
        {product.description && (
          <Text style={styles.description}>
            Ingrediente: {product.description}
          </Text>
        )}

        <Text style={styles.price}>{product.price}</Text>

        {product.purchase_url && (
          <TouchableOpacity style={styles.button} onPress={handlePress}>
            <Text style={styles.buttonText}>Ver producto</Text>
          </TouchableOpacity>
        )}
      </View>
    </View>
  );
};
```

---

## Ejemplo completo del flujo

```javascript
// 1. LLM devuelve esto:
const diagnosisResult = {
  disease: "Roya",
  confidence: 0.91,
  description: "Se detectan síntomas compatibles con roya.",
};

const selectedCrop = "Maíz";

// 2. Frontend llama al servicio:
POST http://44.196.107.153/products/recommend
Headers: { "Content-Type": "application/json", "X-API-Key": "..." }
Body:    { "disease": "Roya", "crop": "Maíz" }

// 3. Servicio responde:
{
  "success": true,
  "disease": "Roya",
  "crop": "Maíz",
  "product_type": "fungicida",
  "products": [ ...hasta 10 productos ordenados por precio... ]
}
```

---

## Errores posibles

| HTTP Status | Causa | Solución |
|---|---|---|
| `401 Unauthorized` | Falta el header `X-API-Key` o es inválido | Verificar que el header esté incluido en todos los requests |
| `422 Unprocessable Entity` | El body no tiene el campo `disease` | Asegurarse de enviar `disease` en el body |
| `500 Internal Server Error` | Error del servidor | Reintentar 1 vez después de 2 segundos |
| Timeout (sin respuesta) | El servidor tardó más de 8s | Mostrar estado de error, no bloquear la UI |

### Respuesta de error de autenticación

```json
{
  "error": "invalid_api_key",
  "message": "API key is missing or invalid"
}
```

---

## Verificación rápida (curl)

Antes de integrar, el desarrollador puede probar el endpoint directamente:

```bash
curl -s -X POST "http://44.196.107.153/products/recommend" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: TU_API_KEY" \
  -d '{"disease": "Mildiu", "crop": "Tomate"}' | python3 -m json.tool
```

Respuesta esperada: JSON con `"success": true` y array `products` con productos.

---

## Consideraciones de seguridad

- La `API_KEY` **no debe estar hardcodeada** en el código fuente del frontend
- Usar variables de entorno o un archivo `.env` que no se suba al repositorio
- En React Native con Expo: usar `expo-constants` o `react-native-config`

```javascript
// Con react-native-config
import Config from "react-native-config";
const API_KEY = Config.SCRAPING_API_KEY;

// Con Expo
import Constants from "expo-constants";
const API_KEY = Constants.expoConfig.extra.scrapingApiKey;
```
