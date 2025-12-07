import pandas as pd
import numpy as np
import logging
from typing import Dict, Optional

# Configurar logging
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(levelname)s - %(message)s',
    filename="trasform.log",
    filemode="w"            
)

# ======================================================================
# CONSTANTES
# ======================================================================
ALTERNATE_KEY_COLS = [
    "product_alternate_key",
    "customer_alternate_key",
    "promotion_alternate_key",
    "currency_alternate_key",
    "sales_territory_alternate_key",
    "reseller_alternate_key",
    "employee_alternate_key"
]

DATE_COLUMNS = ["OrderDate", "DueDate", "ShipDate"]
DATE_KEY_SUFFIXES = ["order_date_key", "due_date_key", "ship_date_key"]

# ======================================================================
# UTILIDADES
# ======================================================================
def normalize_key(df: pd.DataFrame, col: str) -> pd.DataFrame:
    """Normaliza una columna clave convirtiendo a string y eliminando espacios."""
    if col not in df.columns:
        return df
    
    df[col] = df[col].astype("string").fillna("").str.strip()
    return df


def normalize_all_alternate_keys(df: pd.DataFrame) -> pd.DataFrame:
    """Normaliza todas las columnas que contengan 'alternate_key'."""
    for col in df.columns:
        if "alternate_key" in col:
            df[col] = df[col].astype(str)
    return df


def to_datekey(s: pd.Series) -> pd.Series:
    """Convierte una serie de fechas a formato YYYYMMDD entero."""
    return pd.to_datetime(s, errors="coerce").dt.strftime("%Y%m%d").astype(int)


def _safe_merge(
    df: pd.DataFrame, 
    dim: pd.DataFrame, 
    left_key: str, 
    right_alt_key: str, 
    surrogate_key_name: str, 
    validate: str = "m:1"
) -> pd.DataFrame:
    """
    Realiza un merge seguro con validaciones mejoradas.
    
    Args:
        df: DataFrame origen
        dim: DataFrame de dimensión con surrogate keys
        left_key: Columna en df para hacer el join
        right_alt_key: Columna alternate key en dim
        surrogate_key_name: Nombre de la surrogate key en dim
        validate: "m:1", "1:1", "1:m", "m:m" para verificar cardinalidad
    
    Returns:
        DataFrame con la surrogate key agregada
    """
    # Validaciones
    if left_key not in df.columns:
        raise KeyError(f"Falta '{left_key}' en DataFrame. Disponibles: {list(df.columns)}")
    if right_alt_key not in dim.columns:
        raise KeyError(f"Falta '{right_alt_key}' en dimensión. Disponibles: {list(dim.columns)}")
    if surrogate_key_name not in dim.columns:
        raise KeyError(f"Falta surrogate key '{surrogate_key_name}' en dimensión.")
    
    # Validar duplicados
    dim_duplicates = dim[dim[right_alt_key].duplicated(keep=False)]
    if not dim_duplicates.empty:
        logging.warning(f"Cuidado  La dimensión tiene {len(dim_duplicates)} registros duplicados en '{right_alt_key}'")
    
    # Merge
    original_len = len(df)
    df_merged = df.merge(
        dim[[right_alt_key, surrogate_key_name]].drop_duplicates(subset=[right_alt_key]),
        how="left",
        left_on=left_key,
        right_on=right_alt_key,
        validate=validate
    )
    
    # Estadísticas
    matched_count = df_merged[surrogate_key_name].notna().sum()
    unmatched_count = len(df_merged) - matched_count
    match_rate = (matched_count / original_len * 100) if original_len > 0 else 0
    
    logging.info(
        f"Merge {left_key} -> {surrogate_key_name}: "
        f"{matched_count}/{original_len} ({match_rate:.1f}%) emparejados, "
        f"{unmatched_count} sin match"
    )
    
    if unmatched_count > 0:
        if unmatched_count == original_len:
            logging.error(f"Error CRÍTICO: Ningún registro emparejado en merge de {left_key}")
        elif unmatched_count > original_len * 0.1:
            logging.warning(f"Cuidado  Alto porcentaje sin match: {unmatched_count}/{original_len}")
    
    df_merged.drop(columns=[right_alt_key], inplace=True, errors="ignore")
    return df_merged


def _merge_date_dimension(
    df: pd.DataFrame, 
    dim_date: pd.DataFrame, 
    temp_key: str, 
    final_key: str
) -> pd.DataFrame:
    """Helper para merge con dimensión fecha."""
    df = df.merge(
        dim_date[["date_key"]], 
        left_on=temp_key, 
        right_on="date_key",
        how="left",
        validate="m:1"
    )
    df.drop(columns=[temp_key], inplace=True)
    df.rename(columns={"date_key": final_key}, inplace=True)
    return df


def _calculate_derived_metrics(df: pd.DataFrame) -> pd.DataFrame:
    """Calcula métricas derivadas comunes para tablas de hechos."""
    df["discount_amount"] = df.get("unit_price", 0) * df.get("unit_price_discount_pct", 0)
    df["total_product_cost"] = df.get("product_standard_cost", 0) * df.get("order_quantity", 0)
    df["sales_amount"] = df.get("extended_amount", 0) - df["discount_amount"]
    return df


# ======================================================================
# TRANSFORM DIMENSIONS
# ======================================================================

def transform_dim_date(df: pd.DataFrame) -> pd.DataFrame:
    """Transforma dimensión de fecha."""
    keep_cols = [
        'date_key', 'full_date_alternate_key', 'day_number_of_week',
        'day_name_of_week', 'day_number_of_month', 'day_number_of_year',
        'week_number_of_year', 'month_name', 'month_number_of_year',
        'calendar_quarter', 'calendar_year', 'calendar_semester',
        'fiscal_quarter', 'fiscal_year', 'fiscal_semester'
    ]
    result = df[keep_cols].copy()
    print(f"Ok dim_date transformada: {len(result)} registros")
    return result


def transform_dim_currency(df: pd.DataFrame) -> pd.DataFrame:
    """Transforma dimensión de moneda."""
    df["currency_alternate_key"] = df["currency_alternate_key"].fillna("USD")
    print(f"Ok dim_currency: {len(df)} registros")
    return df.copy()


def transform_dim_sales_territory(df: pd.DataFrame) -> pd.DataFrame:
    """Transforma dimensión de territorio de ventas."""
    # Asegurar que sales_territory_key = sales_territory_alternate_key
    result = df.drop(columns=['X'], errors='ignore').copy()
    
    # Si no existe sales_territory_key, crearla a partir de sales_territory_alternate_key
    if 'sales_territory_key' not in result.columns and 'sales_territory_alternate_key' in result.columns:
        result['sales_territory_key'] = result['sales_territory_alternate_key']
    
    expected_cols = [
        'sales_territory_key',  # Ahora incluimos esta columna
        'sales_territory_alternate_key', 
        'sales_territory_region',
        'sales_territory_country', 
        'sales_territory_group'
    ]
    
    # Verificar que tenemos las columnas necesarias
    available_cols = [col for col in expected_cols if col in result.columns]
    result = result[available_cols]
    
    print(f"Ok dim_sales_territory transformada: {len(result)} registros")
    return result


def transform_dim_geography(df: pd.DataFrame, dim_sales_territory: pd.DataFrame) -> pd.DataFrame:
    """Transforma la dimensión de geografía y hace join con sales territory."""
    
    expected_cols = [
        "city",
        "state_province_code", 
        "state_province_name",
        "country_region_code",
        "country_region_name", 
        "postal_code",
        "sales_territory_key"  # Esta es la FK que usaremos para el join
    ]

    if list(df.columns) != expected_cols:
        raise ValueError(f"Estructura incorrecta en dim_geography: {df.columns}")

    # Hacer join con dim_sales_territory para obtener el sales_territory_alternate_key
    if not dim_sales_territory.empty and 'sales_territory_key' in df.columns:
        # Realizar el merge para validar la relación
        original_count = len(df)
        
        df_merged = df.merge(
            dim_sales_territory[['sales_territory_key']],
            on='sales_territory_key',
            how='left',
            indicator=True
        )
        
        # Contar registros que hicieron match
        matched_count = (df_merged['_merge'] == 'both').sum()
        unmatched_count = (df_merged['_merge'] == 'left_only').sum()
        
        logging.info(f"Geography-SalesTerritory join: {matched_count}/{original_count} registros emparejados")
        
        if unmatched_count > 0:
            logging.warning(f"Cuidado  {unmatched_count} registros de geography sin territorio de ventas correspondiente")
        
        # Eliminar la columna temporal de merge
        df = df_merged.drop('_merge', axis=1)

    # Agregar registro Unknown para geografías sin territorio
    unknown_record = {
        "city": "Unknown",
        "state_province_code": "---", 
        "state_province_name": "Unknown",
        "country_region_code": "---",
        "country_region_name": "Unknown", 
        "postal_code": "Unknown",
        "sales_territory_key": None  # Sin territorio asignado
    }

    unknown_df = pd.DataFrame([unknown_record])
    result = pd.concat([df, unknown_df], ignore_index=True)

    print(f"Ok dim_geography transformada: {len(result)} registros (incluye Unknown)")
    return result



def transform_dim_promotion(df: pd.DataFrame) -> pd.DataFrame:
    """Transforma dimensión de promoción."""
    print(f"dim_promotion: {len(df)} registros")
    return df.copy()


def transform_dim_sales_reason(df: pd.DataFrame) -> pd.DataFrame:
    """Transforma dimensión de razón de venta."""
    print(f"dim_sales_reason: {len(df)} registros")
    return df.copy()


def transform_dim_product_category(df: pd.DataFrame) -> pd.DataFrame:
    """Transforma dimensión de categoría de producto."""
    print(f"dim_product_category: {len(df)} registros")
    return df.copy()


def transform_dim_product_subcategory(
    df: pd.DataFrame, 
    dim_product_category: pd.DataFrame
) -> pd.DataFrame:
    """Transforma dimensión de subcategoría de producto."""
    df = _safe_merge(
        df, dim_product_category,
        left_key="product_category_alternate_key",
        right_alt_key="product_category_alternate_key",
        surrogate_key_name="product_category_key",
        validate="m:1"
    )
    print(f"dim_product_subcategory: {len(df)} registros")
    return df


def transform_dim_product(
    df: pd.DataFrame,
    dim_product_subcategory: pd.DataFrame
) -> pd.DataFrame:
    """Transforma dimensión de producto."""
    if 'product_subcategory_key' in df.columns:
        df = df.rename(columns={'product_subcategory_key': 'product_subcategory_alternate_key_temp'})
        df = _safe_merge(
            df, dim_product_subcategory,
            left_key="product_subcategory_alternate_key_temp",
            right_alt_key="product_subcategory_alternate_key",
            surrogate_key_name="product_subcategory_key",
            validate="m:1"
        )
        df.drop(columns=['product_subcategory_alternate_key_temp'], inplace=True, errors='ignore')
    
    print(f"dim_product: {len(df)} registros")
    return df


def transform_dim_customer(
    df: pd.DataFrame, 
    dim_geography: pd.DataFrame
) -> pd.DataFrame:
    """Transforma dimensión de cliente."""
    UNKNOWN_GEO_KEY = 10
    
    # Crear copia explícita para evitar SettingWithCopyWarning
    df = df.copy()
    dim_geography = dim_geography.copy()
    
    # Normalizar postal_code
    df['postal_code'] = df['postal_code'].fillna('Unknown')
    dim_geography['postal_code'] = dim_geography['postal_code'].fillna('Unknown')
    
    # Merge
    original_len = len(df)
    df = df.merge(
        dim_geography[['postal_code', 'geography_key']].drop_duplicates(subset=['postal_code']),
        how='left',
        on='postal_code'
    )
    
    # Asignar unknown a registros sin match
    df['geography_key'] = df['geography_key'].fillna(UNKNOWN_GEO_KEY)
    
    # Estadísticas
    matched_count = (df['geography_key'] != UNKNOWN_GEO_KEY).sum()
    unknown_count = (df['geography_key'] == UNKNOWN_GEO_KEY).sum()
    
    logging.info(f"Customer-Geography match: {matched_count}/{original_len} ({matched_count/original_len*100:.1f}%)")
    logging.info(f"Registros con geography Unknown: {unknown_count}")
    
    # Limpiar
    df.drop(columns=['city', 'state_province_code', 'postal_code'], inplace=True, errors='ignore')
    
    print(f"Ok dim_customer: {len(df)} registros")
    print(f" Geography matches: {matched_count} registros") 
    print(f" Geography unknown: {unknown_count} registros")
    
    return df


def transform_dim_reseller(
    df: pd.DataFrame,
    dim_geography: pd.DataFrame
) -> pd.DataFrame:
    """Transforma dimensión de revendedor."""
    # Crear copia explícita para evitar SettingWithCopyWarning
    df = df.copy()
    dim_geography = dim_geography.copy()
    
    # Eliminar duplicados
    duplicates_before = df.duplicated(subset=['reseller_alternate_key']).sum()
    if duplicates_before > 0:
        logging.info(f"Eliminando {duplicates_before} registros duplicados")
        df = df.drop_duplicates(subset=['reseller_alternate_key'], keep='first')
    
    # Normalizar valores nulos
    geo_cols = ['city', 'state_province_code', 'postal_code']
    for col in geo_cols:
        if col in df.columns:
            df[col] = df[col].fillna('Unknown')
        if col in dim_geography.columns:
            dim_geography[col] = dim_geography[col].fillna('Unknown')
    
    # Crear clave compuesta
    df['geo_match_key'] = df['city'].astype(str) + '_' + df['state_province_code'].astype(str) + '_' + df['postal_code'].astype(str)
    dim_geography_temp = dim_geography.copy()
    dim_geography_temp['geo_match_key'] = dim_geography_temp['city'].astype(str) + '_' + dim_geography_temp['state_province_code'].astype(str) + '_' + dim_geography_temp['postal_code'].astype(str)
    
    # Merge
    original_len = len(df)
    df = df.merge(
        dim_geography_temp[['geo_match_key', 'geography_key']].drop_duplicates(),
        how='left',
        on='geo_match_key'
    )
    
    matched_count = df['geography_key'].notna().sum()
    logging.info(f"Reseller-Geography match: {matched_count}/{original_len} ({matched_count/original_len*100:.1f}%)")
    
    # Limpiar
    df.drop(columns=['geo_match_key'] + geo_cols, inplace=True, errors='ignore')
    
    print(f"Ok dim_reseller: {len(df)} registros")
    return df


def transform_dim_employee(df: pd.DataFrame) -> pd.DataFrame:
    """Transforma dimensión de empleado."""
    print(f"Ok dim_employee: {len(df)} registros")
    return df.copy()


# ======================================================================
# TRANSFORM FACTS
# ======================================================================

def transform_fact_internet_sales(
    df: pd.DataFrame,
    dim_product: pd.DataFrame,
    dim_customer: pd.DataFrame,
    dim_promotion: pd.DataFrame,
    dim_currency: pd.DataFrame,
    dim_territory: pd.DataFrame,
    dim_date: pd.DataFrame
) -> pd.DataFrame:
    """Transforma tabla de hechos de ventas por internet."""
    # Normalización
    df = normalize_key(df, "product_alternate_key")
    dim_product = normalize_key(dim_product, "product_alternate_key")
    df["currency_alternate_key"] = df["currency_alternate_key"].fillna("USD")
    
    # Crear date keys directamente desde las columnas OrderDate, DueDate, ShipDate
    date_mappings = [
        ("OrderDate", "order_date_key"),
        ("DueDate", "due_date_key"), 
        ("ShipDate", "ship_date_key")
    ]
    
    for date_col, key_name in date_mappings:
        if date_col in df.columns:
            df[key_name] = to_datekey(df[date_col])
        else:
            logging.warning(f"Cuidado  Columna {date_col} no encontrada en fact_internet_sales")
    
    # Merges con dimensiones
    merge_configs = [
        (dim_product, "product_alternate_key", "product_key"),
        (dim_customer, "customer_alternate_key", "customer_key"),
        (dim_promotion, "promotion_alternate_key", "promotion_key"),
        (dim_currency, "currency_alternate_key", "currency_key"),
        (dim_territory, "sales_territory_alternate_key", "sales_territory_key")
    ]
    
    for dim, alt_key, surr_key in merge_configs:
        df = _safe_merge(df, dim, left_key=alt_key, right_alt_key=alt_key, surrogate_key_name=surr_key)
    
    # Merges con fecha
    for _, final_key in date_mappings:
        if final_key in df.columns:
            df = _merge_date_dimension(df, dim_date, final_key, final_key)
    
    # Limpiar columnas originales de fecha (si existen)
    original_date_cols = ["OrderDate", "DueDate", "ShipDate"]
    df.drop(columns=[col for col in original_date_cols if col in df.columns], inplace=True, errors='ignore')
    
    # Renombrar SalesOrderNumber
    if "SalesOrderNumber" not in df.columns:
        raise ValueError("Error La columna SalesOrderNumber no está presente en fact_internet_sales.")
    df.rename(columns={"SalesOrderNumber": "sales_order_number"}, inplace=True)
    
    # Forzar tipos enteros en surrogate keys
    int_keys = ["product_key", "customer_key", "promotion_key", "currency_key", 
                "sales_territory_key", "order_date_key", "due_date_key", "ship_date_key"]
    for col in int_keys:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int64")
    
    # Cálculos derivados
    df = _calculate_derived_metrics(df)
    
    # Filtrar registros sin claves críticas
    df.dropna(subset=["product_key", "customer_key", "order_date_key"], inplace=True)
    
    return df


def transform_fact_reseller_sales(
    df: pd.DataFrame,
    dim_product: pd.DataFrame,
    dim_reseller: pd.DataFrame,
    dim_employee: pd.DataFrame,
    dim_promotion: pd.DataFrame,
    dim_currency: pd.DataFrame,
    dim_sales_territory: pd.DataFrame,
    dim_date: pd.DataFrame
) -> pd.DataFrame:
    """Transforma tabla de hechos de ventas de revendedor."""
    logging.info("=== Iniciando transformación de fact_reseller_sales ===")
    
    # Normalización
    df = normalize_key(df, "product_alternate_key")
    dim_product = normalize_key(dim_product, "product_alternate_key")
    df["currency_alternate_key"] = df["currency_alternate_key"].fillna("USD")
    
    # Crear date keys directamente desde las columnas OrderDate, DueDate, ShipDate
    date_mappings = [
        ("OrderDate", "order_date_key"),
        ("DueDate", "due_date_key"), 
        ("ShipDate", "ship_date_key")
    ]
    
    for date_col, key_name in date_mappings:
        if date_col in df.columns:
            df[key_name] = to_datekey(df[date_col])
        else:
            logging.warning(f"Cuidado  Columna {date_col} no encontrada en fact_reseller_sales")
    
    # Merges con dimensiones
    merge_configs = [
        (dim_product, "product_alternate_key", "product_key"),
        (dim_reseller, "reseller_alternate_key", "reseller_key"),
        (dim_employee, "employee_alternate_key", "employee_key"),
        (dim_sales_territory, "sales_territory_alternate_key", "sales_territory_key"),
        (dim_promotion, "promotion_alternate_key", "promotion_key"),
        (dim_currency, "currency_alternate_key", "currency_key")
    ]
    
    for dim, alt_key, surr_key in merge_configs:
        df = _safe_merge(df, dim, left_key=alt_key, right_alt_key=alt_key, surrogate_key_name=surr_key, validate="m:1")
    
    # Merges con fecha
    for _, final_key in date_mappings:
        if final_key in df.columns:
            df = _merge_date_dimension(df, dim_date, final_key, final_key)
    
    # Limpiar columnas originales de fecha (si existen)
    original_date_cols = ["OrderDate", "DueDate", "ShipDate"]
    df.drop(columns=[col for col in original_date_cols if col in df.columns], inplace=True, errors='ignore')
    
    # Renombrar SalesOrderNumber
    if "SalesOrderNumber" not in df.columns:
        raise ValueError("Error La columna SalesOrderNumber no está presente.")
    df.rename(columns={"SalesOrderNumber": "sales_order_number"}, inplace=True)
    
    # Cálculos derivados
    df = _calculate_derived_metrics(df)
    
    # Eliminar registros con keys críticos nulos
    critical_keys = ["product_key", "reseller_key", "employee_key", "order_date_key"]
    before_count = len(df)
    df.dropna(subset=critical_keys, inplace=True)
    after_count = len(df)
    
    if before_count > after_count:
        logging.warning(f"Cuidado  Eliminados {before_count - after_count} registros con keys nulos")
    
    logging.info(f"Ok fact_reseller_sales transformada: {len(df)} registros")
    return df


# ======================================================================
# TRANSFORM ALL
# ======================================================================

def transform_all_data(extraction_dict: Dict, csv_data: Dict) -> Dict:
    """Transforma todos los datos extraídos."""
    transformed = {}
    
    # Normalizar alternate keys
    for dfname, df in extraction_dict.items():
        for col in ALTERNATE_KEY_COLS:
            if col in df.columns:
                df[col] = df[col].astype("string")
    
    print("Transformando dimensiones de NIVEL 1 (sin dependencias)...")
    
    # Dimensiones desde CSV primero
    if 'dim_sales_territory' in csv_data and not csv_data['dim_sales_territory'].empty:
        transformed['dim_sales_territory'] = transform_dim_sales_territory(csv_data['dim_sales_territory'])
    
    if 'dim_date' in csv_data and not csv_data['dim_date'].empty:
        transformed['dim_date'] = transform_dim_date(csv_data['dim_date'])
    
    # Dimensiones desde OLTP que dependen de dim_sales_territory
    if 'dim_geography' in extraction_dict and 'dim_sales_territory' in transformed:
        transformed['dim_geography'] = transform_dim_geography(
            extraction_dict['dim_geography'], 
            transformed['dim_sales_territory']
        )
    
    # Resto de dimensiones nivel 1
    level1_dims = [
        ('dim_currency', transform_dim_currency),
        ('dim_promotion', transform_dim_promotion),
        ('dim_sales_reason', transform_dim_sales_reason),
        ('dim_product_category', transform_dim_product_category),
        ('dim_employee', transform_dim_employee)
    ]
    
    for dim_name, transform_func in level1_dims:
        if dim_name in extraction_dict:
            transformed[dim_name] = transform_func(extraction_dict[dim_name])
    
    # Dimensiones con dependencias (sin transformar)
    print("\n Preparando dimensiones con dependencias (se transformarán en carga)...")
    
    dependent_dims = ['dim_product_subcategory', 'dim_product', 'dim_customer', 'dim_reseller']
    for dim_name in dependent_dims:
        if dim_name in extraction_dict:
            transformed[dim_name] = extraction_dict[dim_name]
            print(f"   - {dim_name}: {len(extraction_dict[dim_name])} registros (sin transformar)")
    
    return transformed


def transform_facts_with_dimensions(extraction_dict: Dict, dims_with_keys: Dict) -> Dict:
    """
    Transforma las tablas de hechos usando las dimensiones ya cargadas con surrogate keys.
    """
    transformed_facts = {}
    
    print("\n Transformando tablas de HECHOS...")
    
    # Normalizar todas las alternate keys
    for name, df in {**extraction_dict, **dims_with_keys}.items():
        if name in extraction_dict:
            extraction_dict[name] = normalize_all_alternate_keys(df)
        if name in dims_with_keys:
            dims_with_keys[name] = normalize_all_alternate_keys(df)
    
    # Fact Internet Sales
    if 'fact_internet_sales' in extraction_dict:
        try:
            transformed_facts['fact_internet_sales'] = transform_fact_internet_sales(
                extraction_dict['fact_internet_sales'],
                dims_with_keys['dim_product'],
                dims_with_keys['dim_customer'],
                dims_with_keys['dim_promotion'],
                dims_with_keys['dim_currency'],
                dims_with_keys['dim_sales_territory'],
                dims_with_keys['dim_date']
            )
            print(f"   Ok fact_internet_sales: {len(transformed_facts['fact_internet_sales'])} registros")
        except Exception as e:
            print(f"   Error transformando fact_internet_sales: {e}")
            transformed_facts['fact_internet_sales'] = pd.DataFrame()
    
    # Fact Reseller Sales
    if 'fact_reseller_sales' in extraction_dict:
        try:
            transformed_facts['fact_reseller_sales'] = transform_fact_reseller_sales(
                extraction_dict['fact_reseller_sales'],
                dims_with_keys['dim_product'],
                dims_with_keys['dim_reseller'],
                dims_with_keys['dim_employee'],
                dims_with_keys['dim_promotion'],
                dims_with_keys['dim_currency'],
                dims_with_keys['dim_sales_territory'],
                dims_with_keys['dim_date']
            )
            print(f"   Ok fact_reseller_sales: {len(transformed_facts['fact_reseller_sales'])} registros")
        except Exception as e:
            print(f"   Error transformando fact_reseller_sales: {e}")
            transformed_facts['fact_reseller_sales'] = pd.DataFrame()
    
    return transformed_facts