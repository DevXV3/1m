# One M — Offline Transport Routing (Python)

เอนจินค้นหาเส้นทางขับรถ + คำนวณค่าขนส่ง **แบบออฟไลน์** จากข้อมูล OpenStreetMap
ประเทศไทย (ชุดเดียวกับที่แอป AppTransport ใช้). ออกแบบให้ **AI เรียกใช้เป็น tool**
เพื่อตอบคำถามพนักงาน เช่น "ส่งปูนจากอุบลไปวารินฯ รถโม่ ค่าเท่าไหร่".

โค้ดเป็นภาษาอังกฤษล้วน (คอมเมนต์ไทยได้) ตามกฎโปรเจกต์.

## โครงสร้าง

```
routing/
  apptransport_routing/
    graph.py     # อ่าน .pbf -> compact CSR driving graph (numpy) + bidirectional Dijkstra
    router.py    # snap พิกัด -> nearest node, หาเส้นทาง, วัดระยะ/เวลา
    cost.py      # ตารางค่าขนส่งตามประเภทรถ (แก้ได้) -> CostBreakdown (บาท)
    geocode.py   # ค้นชื่อสถานที่ไทย (place/POI) -> พิกัด
    tools.py     # TOOLS (Anthropic tool-use schema) + ToolRunner.dispatch()
  build_index.py         # สร้าง cache/thailand_graph.npz (ครั้งเดียว)
  build_places.py        # สร้าง cache/places.json (ครั้งเดียว)
  cli.py                 # ใช้งานผ่านคอมมานด์ไลน์
  example_claude_client.py  # ตัวอย่างให้ Claude เรียก tool
```

## ติดตั้ง (ครั้งเดียว)

```powershell
cd C:\Users\AiMiniX\DevXV3\one-m\AppTransport\routing
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install osmium networkx shapely rtree numpy
# สร้าง cache จากไฟล์ pbf ที่ planetiler โหลดไว้แล้ว (mapdata/data/sources/thailand.osm.pbf)
.\.venv\Scripts\python.exe build_index.py    # ~นาที, ได้ cache/thailand_graph.npz
.\.venv\Scripts\python.exe build_places.py   # ~นาที, ได้ cache/places.json
```

> ต้องมีไฟล์ `../mapdata/data/sources/thailand.osm.pbf` (planetiler โหลดไว้ตอนสร้าง
> แผนที่แอป). ถ้าลบไปแล้ว รัน planetiler ใหม่หรือโหลด Geofabrik thailand-latest.osm.pbf.

## ใช้งาน CLI

```powershell
.\.venv\Scripts\python.exe cli.py vehicles
.\.venv\Scripts\python.exe cli.py geocode "วารินชำราบ"
.\.venv\Scripts\python.exe cli.py route 15.2287 104.8564 14.9799 102.0977 --vehicle 10wheel
.\.venv\Scripts\python.exe cli.py plan "เมืองอุบลราชธานี" "เมืองนครราชสีมา" --vehicle mixer --round-trip
```

`plan_transport` คืน: `route` (distance_km, duration_min), `cost` (ค่าขนส่งแยกรายการ),
และ `geometry` (พิกัดเส้นทาง [[lat,lon],...] เอาไปวาดบนแผนที่ MapLibre ได้).

## ให้ AI เรียกใช้

`apptransport_routing.tools.TOOLS` เป็น schema มาตรฐาน tool-use (name/description/
input_schema) ใช้ได้กับ Claude API หรือโมเดล local ที่รับ JSON-schema tools.
`ToolRunner.dispatch(name, input)` รันแล้วคืน dict.

```python
from apptransport_routing.tools import TOOLS, ToolRunner
runner = ToolRunner.from_cache("cache")
runner.dispatch("plan_transport", {
    "origin": "เมืองอุบลราชธานี", "destination": "วารินชำราบ",
    "vehicle_type": "mixer", "round_trip": True,
})
```

ตัวอย่างต่อ Claude เต็ม loop อยู่ใน `example_claude_client.py` (ต้อง `pip install anthropic`
+ ตั้ง `ANTHROPIC_API_KEY`; default model `claude-opus-4-8`, เปลี่ยนเป็น `claude-fable-5`
ได้ถ้าต้องการตัวเก่งสุด). โมเดล local (Qwythos ผ่าน Ollama OpenAI-compatible) ใช้ TOOLS
ชุดเดียวกันได้ — แก้เฉพาะไฟล์ client.

## ปรับอัตราค่าขนส่ง

แก้ `TARIFFS` ใน `apptransport_routing/cost.py` หรือทำไฟล์ JSON แล้วโหลดด้วย
`cost.load_tariffs(path)`. ปัจจุบันมี: pickup, 6wheel, 10wheel, mixer (รถโม่), trailer
— เรตเป็นตัวอย่าง ปรับให้ตรงราคาจริงของบริษัท.

## หมายเหตุทางเทคนิค

- กราฟเก็บเป็น CSR arrays (numpy) โหลดเร็ว กิน RAM น้อยกว่า networkx object.
  ค้นเส้นทางด้วย bidirectional Dijkstra (ถ่วงด้วยเวลา/ระยะ).
- ความเร็วประเมินจาก tag `maxspeed` ถ้ามี ไม่งั้นใช้ค่าตาม highway class
  (motorway 100, primary 70, ... residential 30 กม./ชม.) — เวลาที่ได้เป็นค่าประมาณ.
- geocoder เป็นแบบง่าย (substring + fuzzy) จาก place/POI ที่มีชื่อใน OSM
  ไม่ใช่ full address geocoder — ถ้าให้พิกัดตรงๆ ได้ผลชัวร์กว่า.
