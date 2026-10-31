"""Taiwan equipment protective earth, stranded copper, independent of insulation.

Source: 用戶用電設備裝置規則 93 / table 93-2 (2025-05-09),
https://gazette.nat.gov.tw/EG_FileManager/eguploadpub/eg031085/ch04/type1/gov31/num7/images/AA.pdf
Parallel raceways: article 22(3), full protective conductor in each raceway.
This is equipment PE, not a neutral or a grounding electrode conductor.
"""

PE_TABLE = ((20, 2), (30, 3.5), (60, 5.5), (100, 8), (200, 14),
            (400, 22), (600, 38), (800, 50), (1000, 60), (1200, 80),
            (1600, 100), (2000, 125), (2500, 150), (3000, 200),
            (4000, 250), (5000, 325), (6300, 400))
PE_BASIS = "設備接地：用戶用電設備裝置規則表九三～二，依同迴路NFB安培額定選銅絞線；PVC綠色／綠黃線。並聯分管每管各配完整線徑，不除以並聯組數。"


def equipment_pe(breaker_a, runs=1):
    if breaker_a <= 0:
        return dict(pe_mm2=0, pe_count=0, pe_spec="無需求", pe_basis=PE_BASIS)
    size = next((size for ceiling, size in PE_TABLE if breaker_a <= ceiling), None)
    if size is None:
        return dict(pe_mm2=None, pe_count=runs, pe_spec="超出6300A表列範圍，需專案設計", pe_basis=PE_BASIS)
    return dict(pe_mm2=size, pe_count=runs,
                pe_spec=f"PVC Cu {size:g} mm² × {runs}條（PE）",
                pe_basis=PE_BASIS)
