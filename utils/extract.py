import pandas as pd # type: ignore
from sqlalchemy.engine import Engine # type: ignore

def extract(tables: list, connection: Engine) -> list:
    """
    Generic extraction function for multiple tables
    :param connection: the connection to the database
    :param tables: the tables to extract
    :return: a list of tables in df format
    """
    dataframes = []
    for table in tables:
        df = pd.read_sql_table(table, connection)
        dataframes.append(df)
    return dataframes


def extract_dim_currency(connection: Engine):
    df_currency = pd.read_sql_query('''
        SELECT 
            CurrencyCode as currency_alternate_key,
            Name as currency_name
        FROM Sales.Currency
    ''', connection)
    return df_currency


def extract_dim_geography(connection: Engine):
    df_geography = pd.read_sql_query('''
        SELECT DISTINCT
            a.City as city,
            sp.StateProvinceCode as state_province_code,
            sp.Name as state_province_name,
            cr.CountryRegionCode as country_region_code,
            cr.Name as country_region_name,
            a.PostalCode as postal_code
        FROM Person.Address a
        INNER JOIN Person.StateProvince sp ON a.StateProvinceID = sp.StateProvinceID
        INNER JOIN Person.CountryRegion cr ON sp.CountryRegionCode = cr.CountryRegionCode
        WHERE a.PostalCode IS NOT NULL 
          AND a.City IS NOT NULL
    ''', connection)
    
    return df_geography


def extract_dim_customer(connection: Engine):
    df_customer = pd.read_sql_query('''
        WITH CustomerContacts AS (
            SELECT 
                p.BusinessEntityID,
                MAX(ea.EmailAddress) as EmailAddress,
                MAX(pp.PhoneNumber) as PhoneNumber
            FROM Person.Person p
            LEFT JOIN Person.EmailAddress ea ON p.BusinessEntityID = ea.BusinessEntityID
            LEFT JOIN Person.PersonPhone pp ON p.BusinessEntityID = pp.BusinessEntityID
            GROUP BY p.BusinessEntityID
        ),
        CustomerAddress AS (
            SELECT 
                bea.BusinessEntityID,
                MAX(a.AddressLine1) as AddressLine1,
                MAX(a.AddressLine2) as AddressLine2,
                MAX(a.City) as City,
                MAX(sp.StateProvinceCode) as StateProvinceCode,
                MAX(a.PostalCode) as PostalCode
            FROM Person.BusinessEntityAddress bea
            LEFT JOIN Person.Address a ON bea.AddressID = a.AddressID
            LEFT JOIN Person.StateProvince sp ON a.StateProvinceID = sp.StateProvinceID
            GROUP BY bea.BusinessEntityID
        )
        SELECT 
            c.CustomerID as customer_alternate_key,
            p.Title as title,
            p.FirstName as first_name,
            p.MiddleName as middle_name,
            p.LastName as last_name,
            p.NameStyle as name_style,
            cc.EmailAddress as email_address,
            ca.AddressLine1 as address_line1,
            ca.AddressLine2 as address_line2,
            cc.PhoneNumber as phone,
            p.Suffix as suffix,
            ca.City as city,
            ca.StateProvinceCode as state_province_code,
            ca.PostalCode as postal_code,
            -- Campos por defecto
            CAST(NULL as date) as birth_date,
            'U' as marital_status,
            'U' as gender,
            CAST(NULL as numeric(19,4)) as yearly_income,
            CAST(0 as smallint) as total_children,
            CAST(0 as smallint) as number_children_at_home,
            'Unknown' as education,
            'N' as house_owner_flag,
            CAST(0 as smallint) as number_cars_owned,
            CAST(NULL as date) as date_first_purchase,
            '0-1 Miles' as commute_distance
        FROM Sales.Customer c
        INNER JOIN Person.Person p ON c.PersonID = p.BusinessEntityID
        LEFT JOIN CustomerContacts cc ON p.BusinessEntityID = cc.BusinessEntityID
        LEFT JOIN CustomerAddress ca ON p.BusinessEntityID = ca.BusinessEntityID
        WHERE c.PersonID IS NOT NULL;
    ''', connection)
    return df_customer


def extract_dim_product_category(connection: Engine):
    df_category = pd.read_sql_query('''
        SELECT 
            ProductCategoryID as product_category_alternate_key,
            Name as product_category_name
        FROM Production.ProductCategory
    ''', connection)
    return df_category


def extract_dim_product_subcategory(connection: Engine):
    df_subcategory = pd.read_sql_query('''
        SELECT 
            ProductSubcategoryID as product_subcategory_alternate_key,
            Name as product_subcategory_name,
            ProductCategoryID as product_category_alternate_key
        FROM Production.ProductSubcategory
    ''', connection)
    return df_subcategory


def extract_dim_product(connection: Engine):  # aqui esta mal, revisar query (asquerosa IA)
    df_product = pd.read_sql_query('''
        SELECT 
            p.ProductID as product_alternate_key,
            p.Name as product_name,            
            p.StandardCost as standard_cost,
            p.ListPrice as list_price,
            p.Color as color,
            p.Size as size,
            p.Weight as weight,
            p.DaysToManufacture as days_to_manufacture,
            p.ProductLine as product_line,
            p.Class as class,
            p.Style as style,
            p.SafetyStockLevel as safety_stock_level,
            p.ReorderPoint as reorder_point,
            p.FinishedGoodsFlag as finished_goods_flag,
            pm.Name as model_name,
            COALESCE(pd_en.Description, pd_any.Description, 'No description available') as description,
            p.SellStartDate as sell_start_date,
            p.SellEndDate as sell_end_date,
            p.ProductSubcategoryID as product_subcategory_key,
            p.WeightUnitMeasureCode as weight_unit_measure_code,
            p.SizeUnitMeasureCode as size_unit_measure_code
        FROM Production.Product p
        LEFT JOIN Production.ProductModel pm ON p.ProductModelID = pm.ProductModelID
        -- Descripción en inglés (prioridad)
        OUTER APPLY (
            SELECT TOP 1 pd.Description
            FROM Production.ProductModelProductDescriptionCulture pmpdc
            JOIN Production.ProductDescription pd ON pmpdc.ProductDescriptionID = pd.ProductDescriptionID
            WHERE pmpdc.ProductModelID = pm.ProductModelID 
                AND pmpdc.CultureID = 'en'
        ) pd_en
        -- Cualquier otra descripción (si no hay en inglés)
        OUTER APPLY (
            SELECT TOP 1 pd.Description
            FROM Production.ProductModelProductDescriptionCulture pmpdc
            JOIN Production.ProductDescription pd ON pmpdc.ProductDescriptionID = pd.ProductDescriptionID
            WHERE pmpdc.ProductModelID = pm.ProductModelID 
                AND NOT EXISTS (SELECT 1 FROM Production.ProductModelProductDescriptionCulture 
                            WHERE ProductModelID = pm.ProductModelID AND CultureID = 'en')
        ) pd_any
        WHERE p.ProductID IS NOT NULL
    ''', connection)
    return df_product


def extract_dim_promotion(connection: Engine):
    df_promotion = pd.read_sql_query('''
        SELECT 
            SpecialOfferID as promotion_alternate_key,
            Description as promotion_name,
            DiscountPct as discount_pct,
            Type as promotion_type,
            Category as promotion_category,
            StartDate as start_date,
            EndDate as end_date,
            MinQty as min_qty,
            MaxQty as max_qty
        FROM Sales.SpecialOffer
    ''', connection)
    return df_promotion


def extract_dim_sales_reason(connection: Engine):
    df_reason = pd.read_sql_query('''
        SELECT 
            SalesReasonID as sales_reason_alternate_key,
            Name as sales_reason_name,
            ReasonType as sales_reason_reason_type
        FROM Sales.SalesReason
    ''', connection)
    return df_reason


def extract_dim_reseller(connection: Engine):
    df_reseller = pd.read_sql_query('''
        SELECT 
            s.BusinessEntityID as reseller_alternate_key,
            s.Name as reseller_name,
            pp.PhoneNumber as phone,
            a.AddressLine1 as address_line1,
            a.AddressLine2 as address_line2,
            -- Campos para join con dim_geography
            a.City as city,
            sp.StateProvinceCode as state_province_code,
            a.PostalCode as postal_code,
            -- Campos de XML (valores por defecto)
            'Value Added Reseller' as business_type,
            CAST(NULL as int) as number_employees,
            CAST(NULL as numeric(19,4)) as annual_sales,
            CAST(NULL as varchar(50)) as bank_name,
            CAST(NULL as numeric(19,4)) as annual_revenue,
            CAST(NULL as int) as year_opened
        FROM Sales.Store s
        LEFT JOIN Person.BusinessEntityAddress bea ON s.BusinessEntityID = bea.BusinessEntityID
        LEFT JOIN Person.Address a ON bea.AddressID = a.AddressID
        LEFT JOIN Person.StateProvince sp ON a.StateProvinceID = sp.StateProvinceID
        LEFT JOIN Person.PersonPhone pp ON s.BusinessEntityID = pp.BusinessEntityID
        WHERE s.BusinessEntityID IS NOT NULL
    ''', connection)
    return df_reseller


def extract_dim_employee(connection: Engine):
    df_employee = pd.read_sql_query('''
        WITH CurrentDepartment AS (
            SELECT 
                BusinessEntityID,
                DepartmentID,
                StartDate,
                EndDate
            FROM HumanResources.EmployeeDepartmentHistory edh
            WHERE EndDate IS NULL OR EndDate > CAST(GETDATE() AS DATE)
        ),
        LatestPayRate AS (
            SELECT 
                BusinessEntityID,
                Rate,
                PayFrequency
            FROM HumanResources.EmployeePayHistory eph
            WHERE RateChangeDate = (
                SELECT MAX(RateChangeDate) 
                FROM HumanResources.EmployeePayHistory 
                WHERE BusinessEntityID = eph.BusinessEntityID
            )
        )
        SELECT 
            e.BusinessEntityID as employee_alternate_key,
            p.FirstName as first_name,
            p.LastName as last_name,
            p.MiddleName as middle_name,
            p.NameStyle as name_style,
            p.Title as title,
            e.HireDate as hire_date,
            e.BirthDate as birth_date,
            e.LoginID as login_id,
            ea.EmailAddress as email_address,
            pp.PhoneNumber as phone,
            e.MaritalStatus as marital_status,
            e.SalariedFlag as salaried_flag,
            e.Gender as gender,
            lpr.PayFrequency as pay_frequency,
            lpr.Rate as base_rate,
            e.VacationHours as vacation_hours,
            e.SickLeaveHours as sick_leave_hours,
            e.CurrentFlag as current_flag,
            d.Name as department_name,
            cd.StartDate as start_date,
            cd.EndDate as end_date
        FROM HumanResources.Employee e
        INNER JOIN Person.Person p ON e.BusinessEntityID = p.BusinessEntityID
        LEFT JOIN Person.EmailAddress ea ON p.BusinessEntityID = ea.BusinessEntityID
        LEFT JOIN Person.PersonPhone pp ON p.BusinessEntityID = pp.BusinessEntityID
        LEFT JOIN CurrentDepartment cd ON e.BusinessEntityID = cd.BusinessEntityID
        LEFT JOIN HumanResources.Department d ON cd.DepartmentID = d.DepartmentID
        LEFT JOIN LatestPayRate lpr ON e.BusinessEntityID = lpr.BusinessEntityID
        WHERE e.BusinessEntityID IS NOT NULL
    ''', connection)
    return df_employee


def extract_fact_internet_sales(connection: Engine):
    df_internet_sales = pd.read_sql_query('''
        SELECT 
            sod.SalesOrderDetailID as sales_order_detail_id,
            sod.ProductID as product_alternate_key,
            soh.OrderDate,
            soh.DueDate,
            soh.ShipDate,
            soh.CustomerID as customer_alternate_key,
            sod.SpecialOfferID as promotion_alternate_key,
            COALESCE(cr.ToCurrencyCode, 'USD') as currency_alternate_key,
            soh.TerritoryID as sales_territory_alternate_key,
            soh.SalesOrderNumber,
            soh.RevisionNumber as revision_number,
            sod.OrderQty as order_quantity,
            sod.UnitPrice as unit_price,
            sod.LineTotal as extended_amount,
            sod.UnitPriceDiscount as unit_price_discount_pct,
            p.StandardCost as product_standard_cost,
            soh.TaxAmt as tax_amt,
            soh.Freight as freight,
            sod.CarrierTrackingNumber as carrier_tracking_number
        FROM Sales.SalesOrderHeader soh
        INNER JOIN Sales.SalesOrderDetail sod ON soh.SalesOrderID = sod.SalesOrderID
        INNER JOIN Production.Product p ON sod.ProductID = p.ProductID
        LEFT JOIN Sales.CurrencyRate cr ON soh.CurrencyRateID = cr.CurrencyRateID
        WHERE soh.OnlineOrderFlag = 1
    ''', connection)
    return df_internet_sales


def extract_fact_reseller_sales(connection: Engine):
    df_reseller_sales = pd.read_sql_query('''
        SELECT 
            -- Claves alternas para joins en transformación
            sod.ProductID as product_alternate_key,
            sod.SalesOrderDetailID as sales_order_detail_id,                              
            soh.OrderDate,
            soh.DueDate,
            soh.ShipDate,
            s.BusinessEntityID as reseller_alternate_key,
            soh.SalesPersonID as employee_alternate_key,
            sod.SpecialOfferID as promotion_alternate_key,
            COALESCE(cr.ToCurrencyCode, 'USD') as currency_alternate_key,
            soh.TerritoryID as sales_territory_alternate_key,
            soh.SalesOrderNumber,
            soh.RevisionNumber as revision_number,
            sod.OrderQty as order_quantity,
            sod.UnitPrice as unit_price,
            sod.LineTotal as extended_amount,
            sod.UnitPriceDiscount as unit_price_discount_pct,
            p.StandardCost as product_standard_cost,
            soh.TaxAmt as tax_amt,
            soh.Freight as freight,
            sod.CarrierTrackingNumber as carrier_tracking_number
        FROM Sales.SalesOrderHeader soh
        INNER JOIN Sales.SalesOrderDetail sod ON soh.SalesOrderID = sod.SalesOrderID
        INNER JOIN Production.Product p ON sod.ProductID = p.ProductID
        INNER JOIN Sales.Customer c ON soh.CustomerID = c.CustomerID
        INNER JOIN Sales.Store s ON c.StoreID = s.BusinessEntityID
        LEFT JOIN Sales.CurrencyRate cr ON soh.CurrencyRateID = cr.CurrencyRateID
        WHERE soh.OnlineOrderFlag = 0
    ''', connection)
    return df_reseller_sales


def extract_for_data_warehouse(connection: Engine):
    extraction_functions = {
        'dim_currency': extract_dim_currency,
        'dim_geography': extract_dim_geography,
        'dim_customer': extract_dim_customer,
        'dim_product_category': extract_dim_product_category,
        'dim_product_subcategory': extract_dim_product_subcategory,
        'dim_product': extract_dim_product,
        'dim_promotion': extract_dim_promotion,
        'dim_sales_reason': extract_dim_sales_reason,
        'dim_reseller': extract_dim_reseller,
        'dim_employee': extract_dim_employee,
        'fact_internet_sales': extract_fact_internet_sales,
        'fact_reseller_sales': extract_fact_reseller_sales
    }
    
    extraction_dict = {}
    
    print("🚀 Iniciando extracción...")
    for table_name, extract_func in extraction_functions.items():
        try:
            df = extract_func(connection)
            extraction_dict[table_name] = df
            print(f"✅ {table_name}: {len(df)} registros")
        except Exception as e:
            print(f"❌ Error extrayendo {table_name}: {e}")
            extraction_dict[table_name] = pd.DataFrame()
    
    return extraction_dict


def load_dimensions_from_csv(csv_folder: str):
    csv_data = {}
    
    try:
        dim_date = pd.read_csv(
            f'{csv_folder}/DimDate.csv',
            sep='|',
            encoding='utf-8',
            header=None
        )

        dim_date.columns = [
            'date_key',
            'full_date_alternate_key',
            'day_number_of_week',
            'day_name_of_week',
            'spanish_day_name_of_week',
            'french_day_name_of_week',
            'day_number_of_month',
            'day_number_of_year',
            'week_number_of_year',
            'month_name',
            'spanish_month_name',
            'french_month_name',
            'month_number_of_year',
            'calendar_quarter',
            'calendar_year',
            'calendar_semester',
            'fiscal_quarter',
            'fiscal_year',
            'fiscal_semester'
        ]

        
        csv_data['dim_date'] = dim_date
        print(f"✅ DimDate: {len(dim_date)} registros cargados")

    except Exception as e:
        csv_data['dim_date'] = pd.DataFrame()

    try:
        dim_sales_territory = pd.read_csv(
            f"{csv_folder}/DimSalesTerritory.csv",
            sep='|',
            encoding='utf-16',
            header=None
        )
        dim_sales_territory = dim_sales_territory.iloc[:, 1:6]

        dim_sales_territory.columns = [ # La x es parte de la csv que no sirve muy bien (foto de territory)
            'sales_territory_alternate_key',
            'sales_territory_region',
            'sales_territory_country',
            'sales_territory_group',
            'X'
        ] 

        csv_data['dim_sales_territory'] = dim_sales_territory
        print(f"✅ DimSalesTerritory: {len(dim_sales_territory)} registros cargados")

    except Exception as e:
        print(f"Error cargando DimSalesTerritory: {e}")
        csv_data['dim_sales_territory'] = pd.DataFrame()

    return csv_data

