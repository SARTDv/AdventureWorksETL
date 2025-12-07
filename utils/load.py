import pandas as pd  # type: ignore
import logging
from sqlalchemy import text  # type: ignore
from sqlalchemy.engine import Engine  # type: ignore
from typing import Dict
from utils.transform import *


def _load_to_table(df: pd.DataFrame, 
                   table_name: str, 
                   engine: Engine, 
                   schema: str = 'dw',
                   index: bool = False) -> int:
    
    if df is None or df.empty:
        logging.warning(f"{table_name}: DataFrame vacío, no se cargará nada")
        return 0
    
    try:
        rows_before = _count_rows(table_name, engine, schema)
        
        logging.debug(f"Cargando {table_name}: {len(df)} filas")
        
        df.to_sql(
            name=table_name,
            con=engine,
            schema=schema,
            if_exists='append',
            index=index,
            method='multi',
            chunksize=1000
        )
        
        rows_after = _count_rows(table_name, engine, schema)
        rows_loaded = rows_after - rows_before
        
        logging.info(f"{table_name}: {rows_loaded} registros cargados")
        return rows_loaded
        
    except Exception as e:
        error_msg = f"Error cargando {table_name}: {str(e)}"
        logging.error(error_msg)
        
        logging.info(f"DataFrame - Filas: {len(df)}, Columnas: {list(df.columns)}")
        
        if isinstance(e, ValueError):
            logging.error("Error de valor - verificar tipos de datos")
        elif isinstance(e, ImportError):
            logging.error("Error de importación - verificar dependencias")
        else:
            logging.error(f"Tipo de error: {type(e).__name__}")
        
        raise


def _count_rows(table_name: str, engine: Engine, schema: str = 'dw') -> int:
    try:
        with engine.connect() as conn:
            result = conn.execute(
                text(f"SELECT COUNT(*) FROM {schema}.{table_name}")
            )
            return result.scalar()
    except:
        return 0


def _table_exists(table_name: str, engine: Engine, schema: str = 'dw') -> bool:
    try:
        with engine.connect() as conn:
            result = conn.execute(text(f"""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = '{schema}' 
                    AND table_name = '{table_name}'
                )
            """))
            return result.scalar()
    except:
        return False


def _truncate_table(table_name: str, engine: Engine, schema: str = 'dw'):
    try:
        with engine.connect() as conn:
            conn.execute(text(f"TRUNCATE TABLE {schema}.{table_name} CASCADE"))
            conn.commit()
        logging.info(f" {table_name} truncada")
    except Exception as e:
        logging.warning(f"No se pudo truncar {table_name}: {str(e)}")


def _reload_dimension_with_keys(table_name: str, 
                                 engine: Engine, 
                                 schema: str = 'dw') -> pd.DataFrame:

    try:
        if not _table_exists(table_name, engine, schema):
            logging.warning(f"Tabla {schema}.{table_name} no existe")
            return pd.DataFrame()
        
        query = f"SELECT * FROM {schema}.{table_name}"
        df = pd.read_sql(query, engine)
        logging.info(f"{table_name} recargada desde DW: {len(df)} registros")
        return df
    except Exception as e:
        logging.error(f"Error recargando {table_name}: {str(e)}")
        return pd.DataFrame() 


def load_dim_date(df: pd.DataFrame, engine: Engine, truncate: bool = False) -> pd.DataFrame:
    logging.info("=== Cargando dim_date ===")
    
    if truncate:
        _truncate_table('dim_date', engine)
    
    _load_to_table(df, 'dim_date', engine)
    return _reload_dimension_with_keys('dim_date', engine)


def load_dim_currency(df: pd.DataFrame, engine: Engine, truncate: bool = False) -> pd.DataFrame:
    logging.info("=== Cargando dim_currency ===")
    
    if truncate:
        _truncate_table('dim_currency', engine)
    
    _load_to_table(df, 'dim_currency', engine)
    return _reload_dimension_with_keys('dim_currency', engine)


def load_dim_sales_territory(df: pd.DataFrame, engine: Engine, truncate: bool = False) -> pd.DataFrame:    
    logging.info("=== Cargando dim_sales_territory ===")
    
    if truncate:
        _truncate_table('dim_sales_territory', engine)
    
    _load_to_table(df, 'dim_sales_territory', engine)
    return _reload_dimension_with_keys('dim_sales_territory', engine)


def load_dim_geography(df: pd.DataFrame, engine: Engine, truncate: bool = False) -> pd.DataFrame:
    logging.info("=== Cargando dim_geography ===")
    
    if truncate:
        _truncate_table('dim_geography', engine)
    
    _load_to_table(df, 'dim_geography', engine)
    return _reload_dimension_with_keys('dim_geography', engine)


def load_dim_promotion(df: pd.DataFrame, engine: Engine, truncate: bool = False) -> pd.DataFrame:
    logging.info("=== Cargando dim_promotion ===")
    
    if truncate:
        _truncate_table('dim_promotion', engine)
    
    _load_to_table(df, 'dim_promotion', engine)
    return _reload_dimension_with_keys('dim_promotion', engine)


def load_dim_sales_reason(df: pd.DataFrame, engine: Engine, truncate: bool = False) -> pd.DataFrame:
    logging.info("=== Cargando dim_sales_reason ===")
    
    if truncate:
        _truncate_table('dim_sales_reason', engine)
    
    _load_to_table(df, 'dim_sales_reason', engine)
    return _reload_dimension_with_keys('dim_sales_reason', engine)


def load_dim_product_category(df: pd.DataFrame, engine: Engine, truncate: bool = False) -> pd.DataFrame:
    logging.info("=== Cargando dim_product_category ===")
    
    if truncate:
        _truncate_table('dim_product_category', engine)
    
    _load_to_table(df, 'dim_product_category', engine)
    return _reload_dimension_with_keys('dim_product_category', engine)


def load_dim_employee(df: pd.DataFrame, engine: Engine, truncate: bool = False) -> pd.DataFrame:
    logging.info("=== Cargando dim_employee ===")
    
    if truncate:
        _truncate_table('dim_employee', engine)
    
    _load_to_table(df, 'dim_employee', engine)
    return _reload_dimension_with_keys('dim_employee', engine)


def load_dim_product_subcategory(df: pd.DataFrame, 
                                  dim_product_category: pd.DataFrame,
                                  engine: Engine, 
                                  truncate: bool = False) -> pd.DataFrame:
    
    if dim_product_category.empty:
        logging.error("dim_product_category está vacía - no se puede cargar subcategoría")
        return pd.DataFrame()
    
    logging.info("=== Cargando dim_product_subcategory ===")
    
    df_transformed = transform_dim_product_subcategory(df, dim_product_category)
    
    if truncate:
        _truncate_table('dim_product_subcategory', engine)
    
    _load_to_table(df_transformed, 'dim_product_subcategory', engine)
    return _reload_dimension_with_keys('dim_product_subcategory', engine)


def load_dim_product(df: pd.DataFrame,
                     dim_product_subcategory: pd.DataFrame,
                     engine: Engine, 
                     truncate: bool = False) -> pd.DataFrame:

    logging.info("=== Cargando dim_product ===")

    
    df_transformed = transform_dim_product(df, dim_product_subcategory)
    
    if truncate:
        _truncate_table('dim_product', engine)
    
    _load_to_table(df_transformed, 'dim_product', engine)
    return _reload_dimension_with_keys('dim_product', engine)


def load_dim_customer(df: pd.DataFrame, 
                      dim_geography: pd.DataFrame,
                      engine: Engine, 
                      truncate: bool = False) -> pd.DataFrame:
    
    logging.info("=== Cargando dim_customer ===")


    df_transformed = transform_dim_customer(df, dim_geography)
    
    if truncate:
        _truncate_table('dim_customer', engine)
    
    _load_to_table(df_transformed, 'dim_customer', engine)
    return _reload_dimension_with_keys('dim_customer', engine)


def load_dim_reseller(df: pd.DataFrame,
                      dim_geography: pd.DataFrame,
                      engine: Engine, 
                      truncate: bool = False) -> pd.DataFrame:

    logging.info("=== Cargando dim_reseller ===")
    

    df_transformed = transform_dim_reseller(df, dim_geography)
    
    if truncate:
        _truncate_table('dim_reseller', engine)
    
    _load_to_table(df_transformed, 'dim_reseller', engine)
    return _reload_dimension_with_keys('dim_reseller', engine)


def load_fact_internet_sales(df: pd.DataFrame, engine: Engine, truncate: bool = False) -> int:
    logging.info("=== Cargando fact_internet_sales ===")
    
    if truncate:
        _truncate_table('fact_internet_sales', engine)
    
    rows = _load_to_table(df, 'fact_internet_sales', engine)
    return rows


def load_fact_reseller_sales(df: pd.DataFrame, engine: Engine, truncate: bool = False) -> int:
    logging.info("=== Cargando fact_reseller_sales ===")
    
    if truncate:
        _truncate_table('fact_reseller_sales', engine)
    
    rows = _load_to_table(df, 'fact_reseller_sales', engine)
    return rows


def load_all_dimensions(transformed_dims: Dict[str, pd.DataFrame], 
                        engine: Engine, 
                        truncate: bool = False) -> Dict[str, pd.DataFrame]:
    dims_with_keys = {}
    
    logging.info("="*60)
    logging.info("INICIANDO CARGA DE DIMENSIONES AL DATA WAREHOUSE")
    logging.info("="*60)

    required_dims = [
        'dim_date', 'dim_currency', 'dim_sales_territory', 'dim_promotion',
        'dim_sales_reason', 'dim_product_category', 'dim_geography', 'dim_employee',
        'dim_product_subcategory', 'dim_product', 'dim_customer', 'dim_reseller'
    ]
    
    missing_dims = [dim for dim in required_dims if dim not in transformed_dims]
    if missing_dims:
        logging.error(f"Dimensiones faltantes en datos de entrada: {missing_dims}")
        raise ValueError(f"Dimensiones requeridas faltantes: {missing_dims}")
    
    logging.info("\n--- NIVEL 1: Dimensiones independientes ---")

    dims_with_keys['dim_date'] = load_dim_date(
        transformed_dims['dim_date'], engine, truncate
    )   
    
    dims_with_keys['dim_currency'] = load_dim_currency(
        transformed_dims['dim_currency'], engine, truncate
    )
    
    dims_with_keys['dim_sales_territory'] = load_dim_sales_territory(
        transformed_dims['dim_sales_territory'], engine, truncate
    )
    
    dims_with_keys['dim_promotion'] = load_dim_promotion(
        transformed_dims['dim_promotion'], engine, truncate
    )
    
    dims_with_keys['dim_sales_reason'] = load_dim_sales_reason(
        transformed_dims['dim_sales_reason'], engine, truncate
    )
    
    dims_with_keys['dim_product_category'] = load_dim_product_category(
        transformed_dims['dim_product_category'], engine, truncate
    )
    
    dims_with_keys['dim_geography'] = load_dim_geography(
        transformed_dims['dim_geography'], engine, truncate
    )
    
    dims_with_keys['dim_employee'] = load_dim_employee(
        transformed_dims['dim_employee'], engine, truncate
    )
    
    
    logging.info("\n--- NIVEL 2: Dimensiones con una dependencia ---")
    
    dims_with_keys['dim_product_subcategory'] = load_dim_product_subcategory(
        transformed_dims['dim_product_subcategory'], 
        dims_with_keys['dim_product_category'],
        engine, 
        truncate
    )
    

    logging.info("\n--- NIVEL 3: Dimensiones con dependencias ---")
    
    dims_with_keys['dim_product'] = load_dim_product(
        transformed_dims['dim_product'],             
        dims_with_keys['dim_product_subcategory'],  
        engine, 
        truncate
    )
    
    dims_with_keys['dim_customer'] = load_dim_customer(
        transformed_dims['dim_customer'],             
        dims_with_keys['dim_geography'],              
        engine, 
        truncate
    )
    
    dims_with_keys['dim_reseller'] = load_dim_reseller(
        transformed_dims['dim_reseller'],      
        dims_with_keys['dim_geography'],  
        engine, 
        truncate
    )
    
    logging.info("\n" + "="*60)
    logging.info("CARGA DE DIMENSIONES COMPLETADA")
    logging.info("="*60)
    
    return dims_with_keys


def load_all_facts(transformed_facts: Dict[str, pd.DataFrame], 
                   engine: Engine, 
                   truncate: bool = False) -> Dict[str, int]:
    stats = {}
    
    logging.info("\n" + "="*60)
    logging.info("INICIANDO CARGA DE TABLAS DE HECHOS AL DATA WAREHOUSE")
    logging.info("="*60)
    
    stats['fact_internet_sales'] = load_fact_internet_sales(
        transformed_facts['fact_internet_sales'], engine, truncate
    )
    
    stats['fact_reseller_sales'] = load_fact_reseller_sales(
        transformed_facts['fact_reseller_sales'], engine, truncate
    )
    
    logging.info("\n" + "="*60)
    logging.info("CARGA DE TABLAS DE HECHOS COMPLETADA")
    logging.info("="*60)
    
    return stats


def load_complete_datawarehouse(transformed_dims: Dict[str, pd.DataFrame],
                                transformed_facts: Dict[str, pd.DataFrame],
                                engine: Engine,
                                truncate: bool = False) -> Dict:

    logging.info("\n" + "="*70)
    logging.info("INICIANDO PROCESO DE CARGA COMPLETO DEL DATA WAREHOUSE")
    logging.info("="*70)
    
    dims_with_keys = load_all_dimensions(transformed_dims, engine, truncate)
    
    fact_stats = load_all_facts(transformed_facts, engine, truncate)
    
    summary = {
        'dimensions_loaded': len(dims_with_keys),
        'facts_loaded': len(fact_stats),
        'total_fact_records': sum(fact_stats.values()),
        'fact_stats': fact_stats
    }
    
    logging.info("\n" + "="*70)
    logging.info("RESUMEN DE CARGA")
    logging.info("="*70)
    logging.info(f"Dimensiones cargadas: {summary['dimensions_loaded']}")
    logging.info(f"Tablas de hechos cargadas: {summary['facts_loaded']}")
    logging.info(f"Total de registros en hechos: {summary['total_fact_records']:,}")
    logging.info("\nDetalle de hechos:")
    for table, count in fact_stats.items():
        logging.info(f"  - {table}: {count:,} registros")
    logging.info("="*70)
    logging.info("PROCESO DE CARGA COMPLETADO EXITOSAMENTE")
    logging.info("="*70)
    
    return summary

def validate_datawarehouse(engine: Engine, schema: str = 'dw') -> pd.DataFrame:
    logging.info("\n=== Validando Data Warehouse ===")
    
    tables = [
        'dim_date', 'dim_currency', 'dim_sales_territory', 'dim_geography',
        'dim_promotion', 'dim_sales_reason', 'dim_product_category',
        'dim_product_subcategory', 'dim_product', 'dim_customer',
        'dim_reseller', 'dim_employee', 'fact_internet_sales', 'fact_reseller_sales'
    ]
    
    stats = []
    for table in tables:
        try:
            count = _count_rows(table, engine, schema)
            table_exists = _table_exists(table, engine, schema)
            
            if not table_exists:
                status = 'No existe'
            elif count > 0:
                status = 'OK'
            else:
                status = 'Vacía'
                
            stats.append({
                'table': table,
                'exists': table_exists,
                'row_count': count,
                'status': status
            })
        except Exception as e:
            stats.append({
                'table': table,
                'exists': False,
                'row_count': 0,
                'status': f'Error: {str(e)}'
            })
    
    df_stats = pd.DataFrame(stats)
    logging.info("\n" + df_stats.to_string(index=False))
    
    # Resumen
    total_tables = len(tables)
    tables_exist = len([s for s in stats if s['exists']])
    tables_loaded = len([s for s in stats if s['row_count'] > 0])
    
    logging.info(f"\nRESUMEN:")
    logging.info(f"   - Tablas existentes: {tables_exist}/{total_tables}")
    logging.info(f"   - Tablas con datos: {tables_loaded}/{total_tables}")
    
    return df_stats


def check_foreign_key_integrity(engine: Engine, schema: str = 'dw'):

    logging.info("\n=== Verificando integridad referencial ===")
    
    checks = [
        {
            'name': 'Internet Sales - Product',
            'query': f"""
                SELECT COUNT(*) FROM {schema}.fact_internet_sales fis
                LEFT JOIN {schema}.dim_product p ON fis.product_key = p.product_key
                WHERE p.product_key IS NULL AND fis.product_key IS NOT NULL
            """
        },
        {
            'name': 'Internet Sales - Customer',
            'query': f"""
                SELECT COUNT(*) FROM {schema}.fact_internet_sales fis
                LEFT JOIN {schema}.dim_customer c ON fis.customer_key = c.customer_key
                WHERE c.customer_key IS NULL AND fis.customer_key IS NOT NULL
            """
        },
        {
            'name': 'Internet Sales - Date',
            'query': f"""
                SELECT COUNT(*) FROM {schema}.fact_internet_sales fis
                LEFT JOIN {schema}.dim_date d ON fis.order_date_key = d.date_key
                WHERE d.date_key IS NULL AND fis.order_date_key IS NOT NULL
            """
        },
        {
            'name': 'Reseller Sales - Product',
            'query': f"""
                SELECT COUNT(*) FROM {schema}.fact_reseller_sales frs
                LEFT JOIN {schema}.dim_product p ON frs.product_key = p.product_key
                WHERE p.product_key IS NULL AND frs.product_key IS NOT NULL
            """
        },
        {
            'name': 'Reseller Sales - Reseller',
            'query': f"""
                SELECT COUNT(*) FROM {schema}.fact_reseller_sales frs
                LEFT JOIN {schema}.dim_reseller r ON frs.reseller_key = r.reseller_key
                WHERE r.reseller_key IS NULL AND frs.reseller_key IS NOT NULL
            """
        },
        {
            'name': 'Reseller Sales - Employee',
            'query': f"""
                SELECT COUNT(*) FROM {schema}.fact_reseller_sales frs
                LEFT JOIN {schema}.dim_employee e ON frs.employee_key = e.employee_key
                WHERE e.employee_key IS NULL AND frs.employee_key IS NOT NULL
            """
        }
    ]
    
    all_ok = True
    with engine.connect() as conn:
        for check in checks:
            try:
                result = conn.execute(text(check['query']))
                orphans = result.scalar()
                
                if orphans == 0:
                    status = "OK"
                else:
                    status = f"{orphans} registros huérfanos"
                    all_ok = False
                
                logging.info(f"{check['name']}: {status}")
            except Exception as e:
                logging.error(f"Error en {check['name']}: {str(e)}")
                all_ok = False
    
    if all_ok:
        logging.info("\nIntegridad referencial: TODOS LOS CHECKS PASARON")
    else:
        logging.warning("\nIntegridad referencial: ALGUNOS CHECKS FALLARON")
    
    return all_ok