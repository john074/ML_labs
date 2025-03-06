import csv
import pandas as pd


def read_with_csv(file_name):
    data = []
    with open(file_name, "r") as f:
        reader = csv.reader(f, delimiter=",")
        for i in reader:
            data.append(i)
    return data

def save_csv(file_name, data):
    with open(file_name, 'w', newline='') as file:
        writer = csv.writer(file)
        writer.writerows(data)

def custom_split(text):
    within_commas = False
    current_word = ""
    res = []
    for i in text:
        if i == "," and len(current_word) != 0 and not within_commas:
            res.append(current_word)
            current_word = ""
        elif i == '"':
            within_commas = not within_commas
        else:
            current_word += i
    res.append(current_word)
    return res

def mode(data):
    most_common = ""
    most_common_count = 0
    for i in range(len(data)):
        count = data.count(data[i])
        if count > most_common_count:
            most_common = data[i]
            most_common_count = count
    return most_common


def clean_data(data):
    headers = data[0]
    headers[4] = "Offered Floor"
    headers.insert(5, "Total Floors")
    rows = data[1:]

    # индексы столбцов
    city_idx = headers.index("City")
    posted_on_idx = headers.index("Posted On")
    area_type_idx = headers.index("Area Type")
    area_locality_idx = headers.index("Area Locality")

    # убираем слепившиеся строки
    for i in range(len(rows)):
        if len(rows[i]) == 1:
            rows[i] = custom_split(rows[i][0])

    # разбиваем колонку с этажами на 2
    for i in range(len(rows)):
        rows[i] = rows[i][:5] + ["null"] + rows[i][5:]
        if "out of" in rows[i][4]:
            rows[i][5] = rows[i][4].split()[-1]
            rows[i][4] = rows[i][4].split()[0]

    # приводим строковые записи об этажах в числовые
    for i in range(len(rows)):
        if rows[i][4].lower() == "ground":
            rows[i][4] = "0"
        elif "lower" in rows[i][4].lower():
            rows[i][4] = "-2"
        elif "upper" in rows[i][4].lower():
            rows[i][4] = "-1"

        if "null" in rows[i][4].lower():
            continue
        # приводим в российский формат
        rows[i][4] = str(int(rows[i][4]) + 1)

        if "null" in rows[i][5].lower():
            continue
        # проверяем чтобы этаж не был выше здания
        if int(rows[i][4]) > int(rows[i][5]):
            rows[i][4], rows[i][5] = rows[i][5], rows[i][4]

    # заполняем отсутствующие значения City и Posted On
    for i in range(1, len(rows)):
        for idx in [city_idx, posted_on_idx]:
            if any(j in rows[i][idx].lower() for j in ["null", "ejkend"]):
                rows[i][idx] = rows[i - 1][idx]

    # заполняем Area Type
    city_area_mapping = {}
    for row in rows:
        city, area_locality, area_type = row[city_idx], row[area_locality_idx], row[area_type_idx]
        if city not in city_area_mapping:
            city_area_mapping[city] = {}
        if "null" not in area_locality.lower() and "null" not in area_type.lower():
            city_area_mapping[city][area_locality] = area_type

    for i in range(len(rows)):
        city, area_locality, area_type = rows[i][city_idx], rows[i][area_locality_idx], rows[i][area_type_idx]
        if not area_type or "null" in area_type.lower():
            if area_locality in city_area_mapping.get(city, {}):
                rows[i][area_type_idx] = city_area_mapping[city][area_locality]
            else:
                rows[i][area_type_idx] = rows[i - 1][area_type_idx]

    # группировка по городу, типу района и месяцу
    grouped_data = {}
    for row in rows:
        city, area_type, posted_on = row[city_idx], row[area_type_idx], row[posted_on_idx]
        month = posted_on[:7]
        key = (city, area_type, month)
        if key not in grouped_data:
            grouped_data[key] = []
        grouped_data[key].append(row)

    # заполняем пропуски средними значениями или модой
    for group in grouped_data.values():
        for col_idx in range(len(headers)):
            col_vals = [row[col_idx] for row in group]
            if any("null" in v.lower() for v in col_vals):
                if all(str(v).isdigit() for v in col_vals if "null" not in v.lower()):
                    numeric_vals = [int(v) for v in col_vals if "null" not in v.lower()]
                    fill_value = int(sum(numeric_vals) / len(numeric_vals))
                else:
                    str_vals = [v for v in col_vals if "null" not in v.lower()]
                    fill_value = mode(str_vals)
                for row in group:
                    if "null" in row[col_idx].lower():
                        row[col_idx] = fill_value

    # объединяем все группы обратно
    rows = [row for group in grouped_data.values() for row in group]

    # собираем выбросы
    outliers = []
    outliers += detect_outliers_iqr([rows[i][2] for i in range(len(rows))])
    outliers += detect_outliers_iqr([rows[i][3] for i in range(len(rows))])
    outliers += detect_outliers_z_score([rows[i][2] for i in range(len(rows))])
    outliers += detect_outliers_z_score([rows[i][3] for i in range(len(rows))])
    outliers = set(outliers)

    # удаляем выбросы
    rows = [row for i, row in enumerate(rows) if i not in outliers]

    final_data = [headers] + rows
    return final_data


def detect_outliers_iqr(values):
    values = [int(i) for i in values]
    values = sorted(values)
    q1 = values[len(values) // 4]
    q3 = values[(len(values) * 3) // 4]
    iqr = q3 - q1
    lower = q1 - 3 * iqr
    upper = q3 + 3 * iqr
    return [v for v in range(len(values)) if values[v] < lower or values[v] > upper]

def detect_outliers_z_score(values, threshold=3):
    values = [int(i) for i in values]
    avg = sum(values) / len(values)
    std_dev = (sum((x - avg) ** 2 for x in values) / len(values)) ** 0.5
    return [i for i in range(len(values)) if abs((values[i] - avg) / std_dev) > threshold]


save_csv("output.csv", clean_data(read_with_csv("1br.csv")))

def categorize_rent(value):
    if value < 15000:
        return "Low"
    elif 15000 <= value < 45000:
        return "Medium"
    elif 45000 <= value < 90000:
        return "High"
    else:
        return "Premium"


df = pd.read_csv("output.csv")
metadata = {i: categorize_rent(df.loc[i, "Rent"]) for i in df.index}

hdf5_file = "converted_data.h5"
with pd.HDFStore(hdf5_file, mode="w") as store:
    store.put("dataset", df, format="table")
    store.get_storer("dataset").attrs.rent_categories = metadata

df = pd.read_hdf(hdf5_file, key="dataset")
with pd.HDFStore(hdf5_file) as store:
    rent_categories = store.get_storer("dataset").attrs.rent_categories

df["Rent Category"] = df.index.map(rent_categories)
columns = df.columns.tolist()
rent_index = columns.index("Rent")
columns.insert(rent_index + 1, columns.pop(columns.index("Rent Category")))
df = df[columns]

pd.set_option("display.width", 300)
pd.set_option("display.max_columns", None)
pd.set_option("display.max_rows", None)
print(df)




