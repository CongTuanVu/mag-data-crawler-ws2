"""Thu ảnh minh hoạ cho trang hồ sơ của 1 aerotropolis.

Với mỗi MỤC trình bày, lấy ảnh đại diện (og:image, fallback ảnh lớn đầu tiên) từ
trang đã crawl tương ứng -> tải -> nén/resize -> lưu html/assets/<case>/<mục>.jpg
và ghi images.json (mục -> file, source_image, page_url, caption).

build_html.py sẽ đọc images.json và nhúng ảnh (base64) vào đúng mục.

Chạy:
    python html/harvest_images.py --name schiphol
"""
from __future__ import annotations

import argparse
import io
import json
import re
import sys
import time
from pathlib import Path

import requests
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
from PIL import Image

try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                         "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"}

# Mục trình bày -> (slug trang nguồn, caption[, want]).
#   want = chuỗi con của URL/alt để chỉ ĐÚNG ảnh cần lấy.
# Bỏ trống `want` sẽ rơi về og:image — gần như luôn là ảnh thương hiệu chung, SAI
# ngữ cảnh mục. Chạy `--inspect` để xem ứng viên thật trước khi điền.
CURATION = {
    "shanghai_hongqiao": [
        ("hero",       "13_wikipedia_shanghai_hongqiao_international_airport", "Sân đỗ máy bay sân bay quốc tế Hồng Kiều", "Airport_Shanghai-Hongqiao_1"),
        ("planning",   "01_overview_shanghai_hongqiao_intl_cbd_official",      "Quy hoạch phát triển công nghiệp Hồng Kiều CBD", "1705481069"),
        ("vision",     "03_development_plan_for_hongqiao_intl_cbd_and_surroun", "Bản quy hoạch Hồng Kiều CBD và vùng phụ cận", "1757668188139049275"),
        ("experience", "13_wikipedia_shanghai_hongqiao_international_airport", "Sảnh đến Nhà ga T1", "201901_Arrival_Floor_Interior"),
    ],
    "zurich": [
        ("hero",       "15_wikipedia_zurich_airport",                 "Toàn cảnh trên không sân bay Zurich", "Aerial_view_of_the_Zurich_Airport"),
        ("planning",   "13_the_circle_convention_center_kh_ng_gian_s_ki_n", "Tổng thể khu The Circle cạnh nhà ga sân bay", "SV-23-CH_Total_HighRes"),
        ("vision",     "02_the_circle_about_the_circle",              "The Circle — tổ hợp LEED Platinum lớn nhất châu Âu", "giorgio-engeli-v1"),
        ("experience", "03_the_circle_rent_danh_m_c_m_t_b_ng_cho_thu", "Không gian coworking 'Spaces' tại The Circle", "spaces_thecircle"),
    ],
    "vienna": [
        ("hero",       "02_airportcity_advantages_facts",              "Phối cảnh 3D toàn khu AirportCity Vienna", "airportcity 3d plan"),
        ("planning",   "15_wikipedia_vienna_international_airport_en", "Bản đồ quy hoạch đường băng thứ ba", "Vie-planned_third_runway"),
        ("vision",     "14_swietelsky_groundbreaking_office_park_4_next", "Phối cảnh Office Park 4 Next", "rendering-office-park-4-next"),
        ("experience", "11_vienna_airport_hotel_conferences_offices",  "Phòng khách sạn Moxy trong AirportCity", "hotel room at the moxy"),
    ],
    "istanbul": [
        ("hero",       "01_i_ga_istanbul_airport_city",   "Istanbul Airport City nhìn từ xa", "airport_city_banner"),
        ("planning",   "14_turkish_cargo_smartist_hub",   "Vị trí chiến lược của trung tâm hàng hoá SmartIST", "smartistuniquelocationmap"),
        ("vision",     "14_turkish_cargo_smartist_hub",   "Tổ hợp hàng hoá thông minh SmartIST", "smartist_gallery_image_1"),
        ("experience", "17_wikipedia_istanbul_airport",   "Nhà ga sân bay Istanbul", "Istanbul_asv2021-11_img72"),
    ],
    "beijing_daxing": [
        ("hero",       "16_wikipedia_beijing_daxing_international_airport_pkx", "Toàn cảnh sân bay quốc tế Đại Hưng Bắc Kinh", "Aerial view of Beijing Daxing"),
        ("planning",   "05_highlights_danh_m_c_9_d_n_t_h_p_tr_ng_i_m_c_a_khu", "Công viên Trụ sở Hàng không Quốc tế trong khu trọng điểm", "17158445086031"),
        ("vision",     "15_zaha_hadid_architects_beijing_daxing_international", "Phối cảnh nhà ga do Zaha Hadid Architects thiết kế", "04128_cr_n320014"),
        ("experience", "16_wikipedia_beijing_daxing_international_airport_pkx", "Sảnh trung tâm nhà ga Đại Hưng", "Beijing_Daxing_International_Airport_13"),
    ],
    "bwi": [
        ("hero",       "09_wikipedia_baltimore_washington_international_airpo", "Toàn cảnh trên không sân bay BWI Marshall", "BWI_Overhead"),
        ("planning",   "10_anne_arundel_county_region_planning_region_1_g_m_b", "Khu văn phòng National Business Park trong vùng quy hoạch Region 1", "National-Business-Park-5"),
        ("vision",     "04_bwi_marshall_economic_impact",                       "Đồ hoạ tác động kinh tế của sân bay BWI", "Thriving-EconomicImpact"),
        ("experience", "09_wikipedia_baltimore_washington_international_airpo", "Nội thất Concourse D", "Concourse_D_at_BWI"),
    ],
    "charlotte_area": [
        ("hero",       "15_wikipedia_charlotte_douglas_international_airport",   "Đường chân trời Charlotte nhìn từ sân bay", "Charlotte_Skyline_from_airport"),
        ("planning",   "12_landdesign_the_river_district_master_plan",           "Quy hoạch tổng thể khu River District (1.400 mẫu)", "River-District-Master-Plan-Vision"),
        ("vision",     "10_the_river_district_trang_ch_nh_th_c_khu_th",          "Định hướng phát triển xanh cho cộng đồng 1.400 mẫu", "istock-1183121151"),
        ("experience", "09_charlotte_regional_business_alliance_clt_airport_f",  "Hành khách tại nhà ga sân bay Charlotte Douglas", "clt_airport_holiday_travel_people"),
    ],
    "chengdu_tianfu": [
        ("hero",       "09_baidu_baike_en_chengdu_tianfu_international_airpor", "Sân bay quốc tế Thiên Phủ Thành Đô", "79f0f736afc379310a55098ecd98a04543a98226bb5a"),
        ("planning",   "09_baidu_baike_en_chengdu_tianfu_international_airpor", "Bản đồ bề mặt giới hạn chướng ngại vật sân bay Thiên Phủ", "4a36acaf2edda3cc7cd9734b60a32e01213fb80e340f"),
        ("vision",     "09_baidu_baike_en_chengdu_tianfu_international_airpor", "Phối cảnh sân bay quốc tế Thiên Phủ", "7e3e6709c93d70cf3bc72a1b0984c600baa1cd11fdd6"),
        ("experience", "10_wikipedia_chengdu_tianfu_international_airport",     "Khu vực đi quốc tế Nhà ga T1", "TFU_T1_IntlDepartures"),
    ],
    "king_salman": [
        ("hero",       "09_designboom_ph_ng_n_th_ng_cu_c_c_a_foster_partners_", "Phương án thắng cuộc của Foster + Partners cho sân bay King Salman", "designboom-02"),
        ("planning",   "09_designboom_ph_ng_n_th_ng_cu_c_c_a_foster_partners_", "Bố cục tổng thể theo phương án Foster + Partners", "designboom-03"),
        ("vision",     "08_vision2030_ai_ph_n_t_ch_t_ng_h_p_ksia",              "KSIA — siêu sân bay định hình lại Riyadh", "king-salman-airport"),
        ("experience", "09_designboom_ph_ng_n_th_ng_cu_c_c_a_foster_partners_", "Không gian nội khu theo thiết kế Foster + Partners", "designboom-04"),
    ],
    "suvarnabhumi": [
        ("hero",       "09_aot_unveils_new_phase_south_terminal_4th_runway",    "AOT công bố giai đoạn mới: nhà ga phía Nam và đường băng thứ 4", "Airports-of-Thailand-Unveils-Ambitious-New-Phase"),
        ("planning",   "04_aotga_multimodal_transportation_center_safz",        "Trung tâm trung chuyển đa phương thức và Khu tự do sân bay (Zone 3)", "line_album_multimodal_zone_3_240611_1"),
        ("vision",     "07_tat_newsroom_aot_pushing_thailand_to_top_aviation_", "AOT đặt mục tiêu đưa Thái Lan lên nhóm đầu trung tâm hàng không", "AOT-Kicks-off-Pushing-Thailand-to-Top"),
        ("experience", "11_wikipedia_airport_rail_link_bangkok",               "Ke ga tuyến Airport Rail Link tại Suvarnabhumi", "Platform_of_ART_Suvarnabhumi_Station"),
    ],
    "tel_aviv": [
        ("hero",       "03_khu_airport_city",                          "Airport City nhìn từ trên cao — phần phía tây", "Israel_AirportCity_FromAir"),
        ("planning",   "06_wikipedia_ben_gurion_airport",              "Sơ đồ đường băng và đường lăn sân bay Ben Gurion", "BenGurionAerodromeChart-2004"),
        ("vision",     "05_airport_city_business_park_h_s_d_n_ti_ng_anh", "Khu công viên doanh nghiệp Airport City", "Airportcity"),
        ("experience", "03_khu_airport_city",                          "Trung tâm văn hoá tại Airport City", "Israel-cultural_center"),
    ],
    "hamilton": [
        ("hero",       "07_engage_hamilton_aegd_secondary_plan_update",          "Khu Tăng trưởng Kinh tế Sân bay Hamilton (AEGD)", "EH_Airport_EGDSP_PrjBanner"),
        ("planning",   "06_city_of_hamilton_aegd_secondary_plan",                "Bản đồ khu vực nghiên cứu Quy hoạch Giao thông Tổng thể AEGD", "masterplan-aegd-map"),
        ("vision",     "06_city_of_hamilton_aegd_secondary_plan",                "Phạm vi nghiên cứu cập nhật Quy hoạch Thứ cấp", "postcard-aegd-secplan-updated"),
        ("experience", "15_vantage_group_49_year_lease_with_city_of_hamilton",   "Sân bay quốc tế John C. Munro Hamilton", "RyanMartin_opt3_1800x1200"),
    ],
    "kansas_city": [
        ("hero",       "09_edgemoor_d_n_nh_ga_m_i_mci_ppp",              "Nhà ga mới sân bay quốc tế Kansas City", "6619a60b4bae06a68752e905"),
        ("planning",   "14_platte_county_edc_c_ng_b_kci_29_logistics_park", "Ảnh trên không khu hậu cần KCI-29", "KCI-29-Logistics-Park-Aerial"),
        ("vision",     "12_kc_smartport_kansas_city_foreign_trade_zones", "Đường chân trời trung tâm Kansas City", "KCSP-WhyKC-1024x683"),
        ("experience", "09_edgemoor_d_n_nh_ga_m_i_mci_ppp",              "Khu bán lẻ và nghệ thuật trong nhà ga mới", "6619a624573744d75a3950c6"),
    ],
    "new_manila": [
        ("hero",       "01_san_miguel_aerocity_inc_trang_ch_ch_nh_th_c",        "Sân bay quốc tế New Manila", "G9iAICSYAZTIdk9scdAAP9CaRzCwupVOVIE339M0"),
        ("planning",   "08_portcalls_asia_smc_unveils_bulacan_aerocity_master", "Quy hoạch ý tưởng Bulacan Aerocity", "Bulacan-aerocity-scaled"),
        ("vision",     "02_san_miguel_aerocity_nmia_project",                   "Phối cảnh sân bay quốc tế New Manila", "t9uKB9QrGc5UOWDgC5Ny0OfCowezqUfeKtZL2qGp"),
        ("experience", "05_smc_infrastructure_new_manila_international_airpor", "Công trình cấp nước phục vụ dự án", "bIBq9HusvBkCkXuMjKfqcXKLFadIC5ZlzGO20ADC"),
    ],
    "shanghai_pudong": [
        ("hero",       "14_wikipedia_shanghai_pudong_international_airport",  "Sân bay quốc tế Phố Đông Thượng Hải (2024)", "Shanghai_Pudong_Airport_2024"),
        ("planning",   "15_wikipedia_airport_link_line_ng_s_t_ngo_i_th_ng_h_i", "Bản đồ tuyến đường sắt nối sân bay Thượng Hải", "Airport_Link_Line"),
        ("vision",     "09_pudong_gov_kh_i_c_ng_nh_ga_t3_s_n_bay_ph_ng",     "Khởi công Nhà ga T3 sân bay Phố Đông", "1732674864737022373"),
        ("experience", "01_eastern_hub_ibcz_c_ng_ch_nh_th_c_shanghai_gov_cn", "Khu thương mại quốc tế miễn thị thực Eastern Hub", "55b5e224144898d974f22e0cdf8ab655"),
    ],
    "cairo": [
        ("hero",       "10_construction_review_terminal_4_cai_3_5_t_usd_cargo", "Nhà ga T4 Cairo — dự án 3,5 tỷ USD thêm 40 triệu khách/năm", "Project-2-546x320"),
        ("planning",   "15_wikipedia_cairo_light_rail_transit",                 "Bản đồ đường sắt nhanh Cairo kết nối sân bay", "Cairo_Rapid_Transit_map"),
        ("vision",     "16_wikipedia_new_administrative_capital",               "Khu Chính phủ tại Thủ đô Hành chính Mới", "Government_District"),
        ("experience", "13_wikipedia_cairo_international_airport",              "Khu miễn thuế Nhà ga T2", "CAI_T2_20200110"),
    ],
    "durban": [
        ("hero",       "01_dube_tradeport_durban_aerotropolis_trang_ch_nh_th_", "Sân bay quốc tế King Shaka và khu vực phụ cận", "aerotropolis_2-3"),
        ("planning",   "07_hatch_durban_aerotropolis_master_plan_duramp",       "Quy hoạch tổng thể Durban Aerotropolis", "Durban-Aerotropolis-Master-Plan"),
        ("vision",     "10_durban_direct_route_development_king_shaka",         "Bờ biển Durban, tỉnh KwaZulu-Natal", "promenade-16aedb09"),
        ("experience", "05_acsa_king_shaka_international_airport",              "Đường băng sân bay King Shaka", "runway"),
    ],
    "addis_ababa_bole": [
        ("hero",       "12_wikipedia_addis_ababa_bole_international_airport",  "Ảnh trên không sân bay Bole (2005)", "AN1002414"),
        ("planning",   "14_wikipedia_addis_ababa_light_rail",                  "Bản đồ đường sắt nhẹ Addis Ababa", "Map_of_the_Addis_Ababa_Light_Rail_Colored"),
        ("vision",     "03_ethiopian_airlines_group_overview_about_ethiopian", "Ethiopian Airlines — tổng quan tập đoàn", "80th-anniversary-web-banner"),
        ("experience", "07_ethiopian_airlines_addis_ababa_stopovers_d_ch_v_t_", "Khách sạn Skylight ngay trong nhà ga", "skylight-hotel_0124"),
    ],
    "beijing_capital": [
        ("hero",       "13_wikipedia_beijing_capital_international_airport",   "Ảnh trên không Nhà ga T1 và T2 sân bay Thủ Đô", "Airport_Overview_JP6592103"),
        ("planning",   "06_beijing_tianzhu_comprehensive_bonded_zone_baidu_ba", "Khu bảo thuế tổng hợp Thiên Trúc, Bắc Kinh", "b999a9014c086e06c0c5310605087bf40ad1cb0a"),
        ("vision",     "04_beijing_investment_promotion_shunyi_district_2025",  "Quận Thuận Nghĩa — vùng phát triển kinh tế sân bay", "W020250909502275909302"),
        ("experience", "13_wikipedia_beijing_capital_international_airport",   "Tàu điện nội khu Nhà ga T3", "APM_18-2-9-17_leaving_ZBAA_T3D"),
    ],
    "narita": [
        ("hero",       "16_wikipedia_narita_international_airport",     "Ảnh trên không sân bay quốc tế Narita (2014)", "Aerial_view_of_Narita_International_Airport_2014"),
        ("planning",   "02_chiba_pref_narita_second_opening_project",   "Bản đồ vùng thúc đẩy trọng điểm quanh sân bay Narita", "juutennsokushinnkuiki"),
        ("vision",     "02_chiba_pref_narita_second_opening_project",   "Phối cảnh nhà ga hành khách mới và khu hàng hoá mới", "shisetuimage7"),
        ("experience", "16_wikipedia_narita_international_airport",     "Hành lang ga tàu Nhà ga T1 Narita", "Narita_Terminal_1_Train_Station"),
    ],
    "haneda_innovation_city": [
        ("hero",       "02_hicity_about_concept_outline",                       "Toàn cảnh khu HANEDA INNOVATION CITY", "concept_img1"),
        ("planning",   "12_fujita_medical_innovation_center_tokyo_hicity_zone", "Bản đồ Zone A — Trung tâm Đổi mới Y tế Fujita", "zone-a_map_02"),
        ("vision",     "02_hicity_about_concept_outline",                       "Sơ đồ khái niệm phát triển HICity", "concept_img3"),
        ("experience", "15_tokyo_international_air_cargo_terminal_facility_ov", "Nhà ga xử lý hàng hoá quốc tế số 1", "overview_img01"),
    ],
    "denver": [
        ("hero",       "15_wikipedia_denver_international_airport",           "Nhà ga Jeppesen nhìn từ trên cao (2025)", "Aerial_view_of_Jeppesen_Terminal"),
        ("planning",   "04_sasaki_den_real_estate_strategic_development_plan", "Bản đồ các cụm phát triển theo quy hoạch chiến lược DEN", "56381_00U_N6_website-1800x1390"),
        ("vision",     "04_sasaki_den_real_estate_strategic_development_plan", "Phối cảnh khu phát triển quanh sân bay Denver", "56381_00U_N8_website-1800x1008"),
        ("experience", "12_fitzsimons_innovation_community_about",             "Phòng thí nghiệm tại Fitzsimons Innovation Community", "about-community"),
    ],
    "orlando": [
        ("hero",       "01_tavistock_development_d_n_lake_nona", "Khu kinh doanh sân bay Lake Nona", "20151104_PMA_1035-2000x1333-1"),
        ("planning",   "09_site_selection_orlando_aerotropolis",  "Bản đồ aerotropolis Orlando — Lake Nona", "21_LakeNona_Orlando_AerotropolisMap"),
        ("vision",     "01_tavistock_development_d_n_lake_nona", "Lake Nona — cộng đồng sống-làm-chơi hướng tương lai", "lake-nona-florida-orlando-future-focused-community"),
        ("experience", "01_tavistock_development_d_n_lake_nona", "Boxi Park tại Lake Nona", "BoxiPark-7488-scaled"),
    ],
    "zhengzhou": [
        ("hero",       "01_baidu_baike_en_zhengzhou_xinzheng_international_ai", "Sân bay quốc tế Tân Trịnh, Trịnh Châu", "b58f8c5494eef01ffd0bef20ecfe9925bc317d3c"),
        ("planning",   "02_quy_ho_ch_ph_t_tri_n_zaez_giai_o_n_13_5_ubnd_t_nh_", "Quy hoạch phát triển Khu Kinh tế Sân bay Trịnh Châu", "6363791282333662502132050"),
        ("vision",     "01_baidu_baike_en_zhengzhou_xinzheng_international_ai", "Nhà ga sân bay Tân Trịnh", "359b033b5bb5c9ea9c2af406d939b6003bf3b37e"),
        ("experience", "01_baidu_baike_en_zhengzhou_xinzheng_international_ai", "Khu vực nhà ga hành khách", "4b90f603738da977015870cebc51f8198718e3e4"),
    ],
    "munich": [
        ("hero",       "13_munich_airport_khai_tr_ng_terminal_1_pier_665_tri_", "Khánh thành Pier Nhà ga T1 — khoản đầu tư 665 triệu euro", "inbetriebnahme-terminal-1-pier"),
        ("planning",   "15_wikipedia_munich_airport",                          "Bản đồ sân bay Munich kèm phần mở rộng theo quy hoạch", "Karte_vom_Flughafen_M"),
        ("vision",     "07_labcampus_the_campus_website_ch_nh_th_c",           "Sơ đồ tổng thể khu đổi mới LabCampus", "labcampus-makroplan"),
        ("experience", "07_labcampus_the_campus_website_ch_nh_th_c",           "Sự kiện cộng đồng tại LabCampus", "Community-Events"),
    ],
    "manchester": [
        ("hero",       "13_invest_manchester_h_s_quy_ho_ch_giai_o_n_1_mix_man", "Khánh thành nhà máy CAF Manchester", "CAF-Manchester-Facility-opening"),
        ("planning",   "14_urban_strategies_masterplan_airport_city_mancheste", "Khung quy hoạch tổng thể Airport City North", "Manchester-EZ-Framework-Update-October-9-2012"),
        ("vision",     "14_urban_strategies_masterplan_airport_city_mancheste", "Các giai đoạn phát triển theo khung quy hoạch", "Phases-1024x793"),
        ("experience", "06_manchester_airport_cargo_world_freight_terminal",   "Ga hàng hoá World Freight Terminal", "world-freight-terminal-406x229"),
    ],
    "madrid_barajas": [
        ("hero",       "01_aena_airport_cities_official_portal",                "Dự án khách sạn sân bay đầu tiên Aena trao thầu tại MAD và BCN", "superdesktop_1920x720-0-1"),
        ("planning",   "03_aena_u_th_u_area_1_airport_city_madrid_barajas",     "Sơ đồ lô đất Área 1 tại trung tâm hàng hoá sân bay Adolfo Suárez", "Satellite"),
        ("vision",     "15_wikipedia_valdebebas_ciudad_aeroportuaria_parque_d", "Ga Valdebebas — hạ tầng kết nối khu đô thị sân bay", "n_de_Valdebebas"),
        ("experience", "14_wikipedia_adolfo_su_rez_madrid_barajas_airport",     "Trần Nhà ga S với kết cấu gỗ đặc trưng", "Ceiling_in_the_S_Terminal"),
    ],
    "guangzhou_baiyun": [
        ("hero",       "15_wikipedia_guangzhou_baiyun_international_airport", "Sân bay Bạch Vân nhìn từ Trạm Vũ trụ Quốc tế", "New_Canton_Airport_under_construction"),
        ("planning",   "15_wikipedia_guangzhou_baiyun_international_airport", "Sơ đồ sân bay Bạch Vân (CAAC)", "Baiyuan_Airport_CAAC_Chart"),
        ("vision",     "15_wikipedia_guangzhou_baiyun_international_airport", "Tháp không lưu sân bay Bạch Vân", "Guangzhou_Baiyun_International_Airport_Control_Tower"),
        ("experience", "15_wikipedia_guangzhou_baiyun_international_airport", "Tác phẩm 'Hạt giống bay' tại sảnh đi Nhà ga T3", "Flying_Seed_Sculpture"),
    ],
    "huntsville": [
        ("hero",       "16_wikipedia_huntsville_international_airport",        "Ảnh trên không sân bay quốc tế Huntsville", "Huntsville_International_Airport_-_January_2016"),
        ("planning",   "01_port_of_huntsville_about",                          "Trung tâm Trung chuyển Quốc tế của Port of Huntsville", "International-Intermodal-Center"),
        ("vision",     "13_huntsville_madison_county_chamber_economic_develop", "Công viên Nghiên cứu Cummings — Viện Công nghệ sinh học HudsonAlpha", "Cummings-Research-Park-HudsonAlpha"),
        ("experience", "16_wikipedia_huntsville_international_airport",        "Khu vực chờ trong nhà ga HSV", "Pic_at_Waiting_Area"),
    ],
    "stockholm": [
        ("hero",       "01_swedavia_airport_city_arlanda", "Phối cảnh Arlanda Airport City tương lai", "City_Airport_Stockhom_Arlanda"),
        ("planning",   "01_swedavia_airport_city_arlanda", "Đô thị sân bay đang hình thành quanh Stockholm Arlanda", "ARN_Flygplatsstad_Kongress"),
        ("vision",     "01_swedavia_airport_city_arlanda", "Quảng trường Arlanda trong tầm nhìn tương lai", "Arlanda_torg"),
        ("experience", "14_wikipedia_stockholm_arlanda_airport", "Khu làm thủ tục Nhà ga T5", "Stockholm-Arlanda_Airport_Terminal_5_c"),
    ],
    "zayed": [
        ("hero",       "07_kezad_group_about_us",                   "Tổng quan khu kinh tế KEZAD quanh sân bay Zayed", "Overview-1"),
        ("planning",   "07_kezad_group_about_us",                   "Quy hoạch tổng thể KEZAD", "Masterplan-KEZAD"),
        ("vision",     "07_kezad_group_about_us",                   "Tầm nhìn của KEZAD Group", "about-img-1"),
        ("experience", "11_wikipedia_zayed_international_airport",  "Nội thất Nhà ga A sân bay quốc tế Zayed", "Terminal_A"),
    ],
    "chicago_o_hare": [
        ("hero",       "15_wikipedia_o_hare_international_airport",           "Sân bay O'Hare nhìn từ Trạm Vũ trụ Quốc tế", "Iss069e037725"),
        ("planning",   "10_illinois_tollway_d_n_i_490_elgin_o_hare_western_ac", "Bản đồ dự án nút giao I-490/IL 390", "aafd6186-9921-b6cf-6994-90f6e086c0d1"),
        ("vision",     "14_world_business_chicago_transportation_distribution", "Đường chân trời Chicago — vùng đô thị mà O'Hare phục vụ", "chicago-illinois-usa-skyline"),
        ("experience", "15_wikipedia_o_hare_international_airport",           "Hành lang United Airlines tại nhà ga O'Hare", "United_Airlines_corridor"),
    ],
    "doha": [
        ("hero",       "02_qatar_free_zones_authority_about", "Toàn cảnh đô thị Doha", "One-Stop-Shop-025d0da0"),
        ("planning",   "01_qfz_ras_bufontas_free_zone",       "Khu đất dịch vụ và kho vận Ras Bufontas nhìn từ trên cao", "Serviced-Land-Plots-413c81c2"),
        ("vision",     "01_qfz_ras_bufontas_free_zone",       "Toà văn phòng hiện đại trong khu tự do Ras Bufontas", "Facilities-e1607727302146-5ebc2f26"),
        ("experience", "06_qfz_aerospace_defense",            "Mặt ngoài nhà ga sân bay Hamad", "aerospace-defense-hamad-airport-hero"),
    ],
    "edmonton": [
        ("hero",       "04_yeg_master_plan_2048",                "Quy hoạch tổng thể YEG 2048 — tháp không lưu sân bay Edmonton", "homepage-carousel-en-generic"),
        ("planning",   "07_leasing_and_land_development_yeg",    "Bản đồ Airport City Edmonton", "Real-Estate-Ad_2023_Map_1920x1080"),
        ("vision",     "06_international_cargo_hub_yeg",         "Phối cảnh phát triển tương lai của Trung tâm Hàng hoá Quốc tế", "ICH_Image_web"),
        ("experience", "07_leasing_and_land_development_yeg",    "Trung tâm mua sắm outlet trong khu Airport City", "DSC_0424-1024x683"),
    ],
    "fort_worth_alliance": [
        ("hero",       "16_wikipedia_perot_field_fort_worth_alliance_airport", "Tháp không lưu sân bay Alliance", "Ft.Worth-Alliance_airport_TOWER"),
        ("planning",   "04_alliancetexas_strategic_economic_advantages",       "Mạng lưới hậu cần AllianceTexas: đa phương thức, đường sắt, đường bộ", "strategic-location"),
        ("vision",     "04_alliancetexas_strategic_economic_advantages",       "Tuyến thương mại và Khu Ngoại thương số 196", "economic-benefits"),
        ("experience", "15_alliancetexas_sustainability",                     "Công viên Bluestem trong khu AllianceTexas", "bluestem-park"),
    ],
    "schiphol": [
        ("hero",       "03_schiphol_business_district",        "Khu Thương mại Schiphol (Business District)"),
        ("planning",   "17_sadc_schiphol_logistics_park",      "Ảnh trên không khu hậu cần Schiphol Logistics Park"),
        ("vision",     "29_schiphol_airport_of_the_future",    "Định hướng 'Sân bay của tương lai'"),
        ("experience", "08_schiphol_real_estate_facilities",   "Tiện ích & không gian trải nghiệm tại Schiphol"),
    ],
    "incheon": [
        ("hero",       "08_incheon_airport_esg_management",                    "Nhà ga hành khách sân bay quốc tế Incheon", "esg-intro-strategy1"),
        ("planning",   "01_incheon_airport_development_of_a_complex_city_air_", "Bản đồ quy hoạch Air City: các phân khu IBC-I/II/III, MRO, logistics, sân golf", "complex-city-view1"),
        ("vision",     "01_incheon_airport_development_of_a_complex_city_air_", "Phối cảnh phân khu IBC-III — giai đoạn phát triển tương lai", "complex-city-view3"),
        ("experience", "17_inspire_entertainment_resort_visitkorea",           "Tổ hợp giải trí INSPIRE trên đảo Yeongjong (nằm trong IBC-III)", "3073488_image2"),
    ],
    "taoyuan": [
        ("hero",       "15_aecom_taoyuan_aerotropolis_development",            "Toàn cảnh sân bay Đào Viên và vùng đô thị sân bay bao quanh", "taoyuan-aerotropolis-1-1"),
        ("planning",   "15_aecom_taoyuan_aerotropolis_development",            "Ranh giới quy hoạch Taoyuan Aerotropolis (4.564 ha) trên nền ảnh thực địa", "taoyuan-aerotropolis-2-new"),
        ("vision",     "02_taoyuan_city_gov_sdgs_aerotropolis_development_pro", "Hồ điều tiết phòng chống thiên tai — 5/12 hồ, sức chứa 1,47 triệu tấn nước", "Disaster Prevention Retention Basin 1"),
        ("experience", "12_taoyuan_tourism_ch_nh_quy_n_tp_airport_mrt",        "Sơ đồ tuyến MRT sân bay A1–A21 với dịch vụ check-in nội đô", "metro_pic"),
    ],
    "western_sydney": [
        ("hero",       "06_bradfield_city_what_is_bradfield_city",             "Toàn cảnh Bradfield City — lõi đô thị của Western Sydney Aerotropolis", "about-bradfield-city-h"),
        ("planning",   "07_bradfield_city_trang_ch_nh",                        "Bản đồ phân khu Bradfield City: Enterprise, AMRF, Central Park, University, Commercial", "city%20spaces%20map"),
        ("vision",     "05_nsw_gov_delivering_bradfield_city",                 "Phối cảnh Bradfield City theo Master Plan duyệt 9/2024", "BDA-artist-impres"),
        ("experience", "06_bradfield_city_what_is_bradfield_city",             "Không gian mở và tiện ích công cộng — 1/3 diện tích thành phố", "Food-and-Beverage-venu"),
    ],
    "dubai_south": [
        ("hero",       "01_dubai_south_trang_ch_ch_nh_th_c",                   "Hệ sinh thái hàng không Dubai South bao quanh sân bay Al Maktoum", "Home_4_Home_Page_slider_1"),
        ("planning",   "04_dubai_south_mbr_aerospace_hub",                     "Sơ đồ quy hoạch khu hàng không MBR Aerospace Hub", "Master_Plan"),
        ("vision",     "01_dubai_south_trang_ch_ch_nh_th_c",                   "Tầm nhìn dài hạn dẫn dắt quá trình phát triển Dubai South", "Home_5_Home_Page_slider_1B"),
        ("experience", "07_dubai_south_live_khu_d_n_c",                        "Khu dân cư ven nước The Pulse Beachfront", "The_Pulse_BeachFrount"),
    ],
    "changi": [
        ("hero",       "07_changi_fact_sheet_terminal_5",                      "Phối cảnh trên không Nhà ga T5 và khu Changi East", "terminal-5-aerial"),
        ("planning",   "06_changi_future_developments",                        "Sơ đồ mặt bằng khu phát triển Changi East", "site-plan"),
        ("vision",     "06_changi_future_developments",                        "Nhà ga T5 — bước mở rộng công suất lên 135 triệu khách/năm", "terminal-5:"),
        ("experience", "08_changi_fact_sheet_jewel",                           "Forest Valley trong Jewel Changi Airport", "forest valley"),
    ],
    "hong_kong": [
        ("hero",       "03_hkia_three_runway_system_t_ng_quan_d_n",            "Toàn cảnh hệ ba đường băng trên đảo Chek Lap Kok", "third-runway-panorama"),
        ("planning",   "03_hkia_three_runway_system_t_ng_quan_d_n",            "Sơ đồ hệ ba đường băng và mặt bằng mở rộng sân bay", "3rs_map_en"),
        ("vision",     "02_hkia_vision_mission_airport_authority",             "Tầm nhìn & sứ mệnh của Airport Authority Hong Kong", "vision_and_mission"),
        ("experience", "05_asiaworld_expo_skycity",                            "SKYCITY — lõi thương mại & giải trí nối thẳng AsiaWorld-Expo", "1600x650-skycity"),
    ],
    "frankfurt": [
        ("hero",       "06_skylineatlas_gateway_gardens",                      "Toàn cảnh khu văn phòng Gateway Gardens cạnh sân bay Frankfurt", "gateway-gardens-frankfurt"),
        ("planning",   "05_gateway_gardens_trang_ch_nh_th_c_khu",              "Khu Gateway Gardens (~35 ha) giữa sân bay Frankfurt và nút giao Frankfurter Kreuz", "main-slider/0"),
        ("vision",     "12_fraport_sustainability",                            "Định hướng phát triển bền vững của Fraport", "AM_05_2022"),
        ("experience", "05_gateway_gardens_trang_ch_nh_th_c_khu",              "Không gian làm việc, khách sạn và tiện ích trong Gateway Gardens", "pages/main/3"),
    ],
    "dfw": [
        ("hero",       "05_dfw_nghi_n_c_u_t_c_ng_kinh_t_78_3_t_usd",           "Sân bay DFW về đêm — cửa ngõ hàng không của vùng Bắc Texas", "Roadway_Terminal_D_Night"),
        ("planning",   "07_wikipedia_dallas_fort_worth_international_airport",  "Sơ đồ mặt bằng sân bay DFW (FAA airport diagram) — 5 nhà ga, 7 đường băng", "FAA airport diagram"),
        ("vision",     "07_wikipedia_dallas_fort_worth_international_airport",  "Ảnh trên không DFW — quỹ đất 17.183 acre lớn hơn Manhattan", "aerial photograph of DFW"),
        ("experience", "07_wikipedia_dallas_fort_worth_international_airport",  "Không gian bán lẻ & ẩm thực trong nhà ga DFW", "Gate C35"),
    ],
    "kuala_lumpur": [
        ("hero",       "01_klia_aeropolis_trang_ch_nh_th_c",                   "KLIA Aeropolis — đô thị sân bay thế kỷ 21 quanh KLIA", "bnr-aeropolis-01"),
        ("planning",   "01_klia_aeropolis_trang_ch_nh_th_c",                   "Sơ đồ vị trí và phạm vi 100 km² của KLIA Aeropolis", "klia-map"),
        ("vision",     "04_klia_aeropolis_aerospace_park",                     "Aerospace Park — cụm hàng không vũ trụ và MRO", "header-Aerospace"),
        ("experience", "05_klia_aeropolis_c_m_mice_leisure",                   "Cụm MICE & Leisure: hội nghị, arena, du lịch sự kiện", "mice-overview"),
    ],
}


def page_url_map(case_dir: Path) -> dict:
    man = case_dir / "manifest.json"
    if not man.exists():
        return {}
    data = json.loads(man.read_text(encoding="utf-8"))
    out = {}
    for s in data.get("sources", []):
        out[s.get("slug", "")] = s.get("url", "")
    return out


def pick_image_url(html_path: Path, page_url: str = "") -> str | None:
    soup = BeautifulSoup(html_path.read_text(encoding="utf-8", errors="ignore"), "html.parser")

    def absolutise(u: str) -> str:
        """Nhiều site trả og:image / src dạng '/path/x.jpg' hoặc './x.jpg'.

        requests không nuốt URL thiếu scheme -> phải ghép với URL trang gốc, nếu
        không sẽ mất ảnh của mọi nguồn dùng đường dẫn tương đối (nsw.gov.au,
        taoyuan-metro…).
        """
        return urljoin(page_url, u) if page_url else u

    og = soup.find("meta", attrs={"property": "og:image"})
    if og and og.get("content"):
        return absolutise(og["content"].strip())
    for i in soup.find_all("img"):
        u = (i.get("src") or i.get("data-src") or "").strip()
        if u and any(e in u.lower() for e in (".jpg", ".jpeg", ".png", ".webp")) \
           and not any(x in u.lower() for x in ("icon", "logo", "sprite", "favicon")):
            return absolutise(u)
    return None


# Từ khoá nhận diện ảnh HỢP NGỮ CẢNH cho từng mục trình bày. Dùng để xếp hạng ứng
# viên ở chế độ --inspect; người curate vẫn là người chốt.
SECTION_HINTS = {
    "hero":       ["aerial", "skyline", "panorama", "overview", "birdseye", "bird-eye",
                   "cityscape", "airport", "toancanh", "空拍", "全景"],
    "planning":   ["masterplan", "master-plan", "master_plan", "zoning", "zone", "precinct",
                   "landuse", "land-use", "map", "plan", "layout", "district", "phankhu",
                   "quyhoach", "規劃", "分區", "地圖"],
    "vision":     ["vision", "future", "render", "concept", "impression", "proposed",
                   "artist", "2050", "2030", "tamnhin", "願景"],
    "experience": ["amenity", "facility", "park", "plaza", "retail", "resort", "leisure",
                   "lifestyle", "community", "interior", "terminal", "station", "tiennich"],
}
JUNK = ("icon", "logo", "sprite", "favicon", "avatar", "placeholder", "blank",
        "spacer", "banner-ad", "share", "btn", "button", "arrow", "menu")


def _px(v) -> int:
    try:
        return int(str(v).strip().replace("px", ""))
    except (TypeError, ValueError):
        return 0


def _largest_srcset(value: str) -> str:
    """URL có bề rộng lớn nhất trong thuộc tính srcset ("a.jpg 400w, b.jpg 1600w")."""
    best, best_w = "", -1
    for part in value.split(","):
        bits = part.split()
        if not bits:
            continue
        w = 0
        if len(bits) > 1:
            d = bits[1].strip().lower()
            if d.endswith("w"):
                w = _px(d[:-1])
            elif d.endswith("x"):        # mật độ điểm ảnh: 2x coi như to hơn 1x
                w = int(float(d[:-1] or 1) * 1000)
        if w > best_w:
            best, best_w = bits[0].strip(), w
    return best


def image_candidates(html_path: Path, page_url: str = "") -> list[dict]:
    """Kiểm kê MỌI ảnh của trang kèm tín hiệu để chọn: alt, kích thước, chữ quanh ảnh.

    Có hàm này vì `og:image` gần như luôn là ảnh chia sẻ mạng xã hội (ảnh thương
    hiệu chung), không phải ảnh minh hoạ đúng mục — vd bản đồ phân khu cho mục
    "Quy hoạch & phân khu". Curate phải nhìn danh sách thật rồi mới chọn.
    """
    soup = BeautifulSoup(html_path.read_text(encoding="utf-8", errors="ignore"), "html.parser")
    absol = (lambda u: urljoin(page_url, u)) if page_url else (lambda u: u)
    out: list[dict] = []
    seen: set[str] = set()

    og = soup.find("meta", attrs={"property": "og:image"})
    if og and og.get("content"):
        u = absol(og["content"].strip())
        seen.add(u)
        out.append({"url": u, "alt": "(og:image — ảnh chia sẻ MXH)", "w": 0, "h": 0,
                    "near": "", "is_og": True})

    for i in soup.find_all("img"):
        u = (i.get("src") or i.get("data-src") or i.get("data-original") or "").strip()
        # `src` thường là bản nhỏ nhất để tải trang cho nhanh; `srcset` mới là nơi
        # trang liệt kê các bản lớn. Lấy bản to nhất ở đây là cách rẻ nhất để có ảnh
        # nét, khỏi phải đoán quy luật đổi URL của từng CDN.
        big = _largest_srcset(i.get("srcset") or i.get("data-srcset") or "")
        if big:
            u = big
        if not u or u.startswith("data:"):
            continue
        u = absol(u)
        if u in seen:
            continue
        seen.add(u)
        # chữ quanh ảnh: figcaption gần nhất, hoặc text của thẻ cha
        near = ""
        fig = i.find_parent("figure")
        if fig and fig.find("figcaption"):
            near = fig.find("figcaption").get_text(" ", strip=True)
        elif i.parent:
            near = i.parent.get_text(" ", strip=True)
        out.append({"url": u, "alt": (i.get("alt") or "").strip(),
                    "w": _px(i.get("width")), "h": _px(i.get("height")),
                    "near": " ".join(near.split())[:110], "is_og": False})
    return out


def score_candidate(c: dict, section: str) -> int:
    """Điểm ưu tiên: khớp từ khoá mục > có alt/caption > không phải ảnh giao diện."""
    hay = f"{c['url']} {c['alt']} {c['near']}".lower()
    s = 0
    for kw in SECTION_HINTS.get(section, []):
        if kw in hay:
            s += 10
    if any(j in c["url"].lower() for j in JUNK):
        s -= 25
    if c["alt"] or c["near"]:
        s += 3
    if c["is_og"]:
        s -= 2          # og:image là phương án chót, không phải phương án đầu
    if max(c["w"], c["h"]) >= 600:
        s += 4
    if 0 < max(c["w"], c["h"]) < 150:
        s -= 12
    if c["url"].lower().endswith(".svg"):
        s -= 8
    return s


def inspect_case(name: str, section_filter: str | None = None) -> None:
    """In bảng ứng viên ảnh cho từng mục — chạy TRƯỚC khi viết CURATION."""
    case_dir = ROOT / "raw_data" / "output" / "ws1_airport" / "raw" / name
    urls = page_url_map(case_dir)
    pages = sorted((case_dir / "pages").glob("*.html"))
    for section in (["hero", "planning", "vision", "experience"]
                    if not section_filter else [section_filter]):
        print(f"\n{'='*78}\nMỤC: {section}   (từ khoá: {', '.join(SECTION_HINTS[section][:6])}…)\n{'='*78}")
        ranked = []
        for p in pages:
            for c in image_candidates(p, urls.get(p.stem, "")):
                sc = score_candidate(c, section)
                if sc > 0:
                    ranked.append((sc, p.stem, c))
        ranked.sort(key=lambda x: -x[0])
        if not ranked:
            print("  (không ứng viên nào khớp từ khoá — dùng --inspect-page để xem toàn bộ)")
        for sc, slug, c in ranked[:8]:
            print(f"  [{sc:>3}] {slug[:46]}")
            print(f"        url : {c['url'][:96]}")
            if c["alt"]:
                print(f"        alt : {c['alt'][:96]}")
            if c["near"]:
                print(f"        near: {c['near'][:96]}")


# Rác mà score_candidate chưa loại hết: ảnh theo dõi, mã QR, nút tải app, và bản đồ
# định vị Wikipedia (luôn là hình nước Y nằm ở đâu — vô nghĩa với hồ sơ một khu).
AUTO_JUNK = re.compile(
    r"qrcode|/beacon|sp\.pl|pixel|(^|/)1x1|app-store|google-play|badge|"
    r"location_map|locator|adm_location|edcp_location|maps\.wikimedia\.org|"
    r"wikipedia-(wordmark|tagline)|enwiki|\.svg(\?|$)", re.I)

SECTIONS = ("hero", "planning", "vision", "experience")

# Số ứng viên giữ lại cho mỗi mục: 1 chính + 7 dự phòng khi ảnh chính hỏng hoặc quá nhỏ.
AUTO_DEPTH = 6

# Sàn tuyệt đối: dưới mức này thì THÀ ĐỂ TRỐNG còn hơn nhét icon 102px vào trang.
# Khác --min-width (ngưỡng "mong muốn", chưa đạt vẫn chấp nhận nếu không còn lựa chọn).
HARD_MIN_W = 400
HARD_MIN_AREA = 400 * 260

# Caption dự phòng khi ảnh không có alt lẫn text xung quanh.
AUTO_CAPTION = {"hero": "Toàn cảnh khu vực sân bay",
                "planning": "Bản đồ / sơ đồ quy hoạch",
                "vision": "Định hướng phát triển",
                "experience": "Hạ tầng và tiện ích trong khu"}


def auto_curation(name: str, case_dir: Path) -> list[tuple]:
    """Tự chọn 4 ảnh cho 1 khu chưa có trong CURATION.

    Dùng lại đúng thang điểm của `--inspect`: mỗi mục lấy ứng viên điểm cao nhất chưa
    bị mục khác chiếm. Trả về tuple 4 phần tử giống CURATION, nhưng `want` là URL đầy
    đủ — khớp chuỗi con với chính nó nên luôn trúng đúng ảnh đã chọn, không cần thêm
    nhánh xử lý nào trong main().
    """
    pages_dir = case_dir / "pages"
    if not pages_dir.is_dir():
        return []
    urls = page_url_map(case_dir)
    pool: list[tuple[dict, str]] = []
    for p in sorted(pages_dir.glob("*.html")):
        for c in image_candidates(p, urls.get(p.stem, "")):
            if not AUTO_JUNK.search(c["url"]):
                pool.append((c, p.stem))

    out, used = [], set()
    for section in SECTIONS:
        ranked = sorted(((score_candidate(c, section), c, slug) for c, slug in pool),
                        key=lambda x: -x[0])
        # điểm <= 0 nghĩa là chỉ còn rác; thà thiếu ảnh còn hơn nhét logo vào
        picks = [(c, slug) for score, c, slug in ranked
                 if score > 0 and c["url"] not in used][:AUTO_DEPTH]
        if not picks:
            continue
        c, slug = picks[0]
        used.add(c["url"])
        caption = (c["alt"] or c["near"] or "").strip()
        caption = caption[:110].rstrip(" .,–-") or AUTO_CAPTION[section]
        alts = [(cc["url"], ss) for cc, ss in picks[1:]]
        out.append((section, slug, caption, c["url"], alts))
    return out


# Wikimedia nhúng thumbnail theo ĐƯỜNG DẪN: .../thumb/a/ab/Ten.jpg/250px-Ten.jpg
WIKI_THUMB_RE = re.compile(r"(/thumb/.+?/)(\d+)px-", re.I)
# WordPress/nhiều CMS thêm hậu tố cỡ vào tên file: ten-1024x683.jpg -> ten.jpg là bản gốc
CMS_SIZE_RE = re.compile(r"-\d{2,4}x\d{2,4}(\.(?:jpe?g|png|webp))$", re.I)


def upsize_url(url: str, want_w: int = 1600) -> str:
    """Nâng tham số bề rộng trên URL ảnh của các CDN/DAM (scene7, Next.js image…)."""
    def bump(m):
        return f"{m.group(1)}={want_w}" if int(m.group(2)) < want_w else m.group(0)
    url = re.sub(r"\b(wid|w)=(\d+)", bump, url)
    url = re.sub(r"\b(hei|h)=(\d+)", lambda m: "", url).replace("&&", "&").rstrip("&?")
    return url


def upsize_variants(url: str) -> list[str]:
    """Các biến thể độ phân giải của CÙNG tấm ảnh, xếp từ to xuống nhỏ.

    Trang gần như luôn nhúng bản thumbnail (`250px-`, `-1024x683`, `wid=250`) của
    đúng tấm ảnh cần; lấy nguyên thumbnail thì hiển thị full-width là vỡ. Đây là đổi
    URL để lấy bản lớn hơn của cùng asset, không phải đổi sang ảnh khác.

    Trả về nhiều bậc vì bản to nhất có thể không tồn tại — Wikimedia trả lỗi nếu xin
    rộng hơn ảnh gốc, còn CMS thì có khi đã xoá bản gốc chỉ giữ các bản đã cắt. Cứ
    thử lần lượt, cuối danh sách luôn là URL nguyên gốc nên không bao giờ tệ hơn cũ.
    """
    out: list[str] = []

    def add(u: str) -> None:
        if u and u not in out:
            out.append(u)

    m = WIKI_THUMB_RE.search(url)
    if m:
        # TUYỆT ĐỐI không đụng tới file gốc trên Commons: nhiều tấm 10-80MB, tải về rồi
        # thu xuống 1100px là phí băng thông và dễ treo khi Wikimedia bóp nhịp. Bản
        # thumbnail 1280px đã thừa cho --max-width 1100.
        # Wikimedia KHÔNG phóng to: xin rộng hơn ảnh gốc thì trả lỗi, nên luôn để bản
        # thumbnail sẵn có làm bậc chót.
        if int(m.group(2)) < 1280:
            add(WIKI_THUMB_RE.sub(lambda mm: f"{mm.group(1)}1280px-", url, count=1))
        add(url)
        return out
    if CMS_SIZE_RE.search(url):
        add(CMS_SIZE_RE.sub(r"\1", url))
    add(upsize_url(url))
    add(url)
    return out


# Chỉ Wikimedia mới chặn theo nhịp. Giãn nhịp cho MỌI host là tự bắn vào chân: mỗi
# ảnh thử tới 5 biến thể độ phân giải, mỗi mục có 8 ứng viên — 1,5s/request nhân lên
# thành hàng phút mỗi khu, dù host kia chẳng hề giới hạn gì.
PACED_HOSTS = ("wikimedia.org", "wikipedia.org")
WIKI_GAP = 2.5
_LAST_HIT: dict[str, float] = {}


# File gốc trên Wikimedia Commons có tấm tới hàng chục MB. `timeout` của requests chỉ
# tính khoảng lặng GIỮA hai gói tin, không giới hạn tổng thời gian, nên một tấm 80MB
# tải chậm sẽ treo vô hạn định. Cắt ở 12MB rồi lùi sang biến thể nhỏ hơn.
MAX_BYTES = 6 * 1024 * 1024


def _read_capped(resp) -> bytes:
    """Đọc body nhưng bỏ ngay khi vượt trần dung lượng."""
    n = resp.headers.get("Content-Length")
    if n and n.isdigit() and int(n) > MAX_BYTES:
        raise ValueError(f"ảnh {int(n) // 1024 // 1024}MB, vượt trần {MAX_BYTES // 1024 // 1024}MB")
    buf = bytearray()
    for chunk in resp.iter_content(65536):
        buf += chunk
        if len(buf) > MAX_BYTES:
            raise ValueError(f"ảnh vượt trần {MAX_BYTES // 1024 // 1024}MB khi đang tải")
    return bytes(buf)


def _pace(url: str) -> None:
    """Chờ tối thiểu 1,5s giữa hai request tới cùng một host bị giới hạn nhịp."""
    host = urlparse(url).netloc.lower()
    if not any(h in host for h in PACED_HOSTS):
        return
    gap = time.monotonic() - _LAST_HIT.get(host, 0.0)
    if gap < WIKI_GAP:
        time.sleep(WIKI_GAP - gap)
    _LAST_HIT[host] = time.monotonic()


def fetch_resize(url: str, max_w: int = 820) -> bytes | None:
    # Hai loại lỗi, hai cách xử lý khác hẳn nhau:
    #  - 429 (Wikimedia chặn theo cụm): PHẢI chờ lâu. Retry-After nó trả về là 10s,
    #    ngắn hơn cooldown thật, nên đi theo header là thua tiếp -> tự lùi 15/30/60s.
    #  - lỗi mạng (host chết, DNS, timeout): chờ lâu vô ích. Thử lại đúng 1 lần rồi
    #    trả lỗi ngay để caller lùi sang ứng viên khác — quan trọng vì mỗi mục có tới
    #    6 ứng viên, chờ lâu ở đây là nhân lên 6 lần.
    _pace(url)
    r = None
    for attempt, wait in enumerate((15, 30, 60, 0)):
        try:
            r = requests.get(url, headers=HEADERS, timeout=20, stream=True)
            if r.status_code != 429 or not wait:
                break
            print(f"      429 — chờ {wait}s rồi thử lại ({attempt + 1}/3)")
        except requests.RequestException as exc:
            if attempt >= 1:      # đã thử lại 1 lần mà vẫn lỗi mạng -> nhường ứng viên khác
                raise
            wait = 3
            print(f"      {type(exc).__name__} — chờ {wait}s rồi thử lại")
        time.sleep(wait)
    r.raise_for_status()
    im = Image.open(io.BytesIO(_read_capped(r))).convert("RGB")
    src_w = im.width
    # KHÔNG phóng to ảnh nhỏ: kéo 143px lên 820px chỉ tạo ảnh mờ nhoè, nặng file mà
    # không thêm chi tiết nào. Caller nhìn src_w để quyết định có lùi ứng viên không.
    src_h = im.height
    if im.width > max_w:
        im = im.resize((max_w, round(im.height * max_w / im.width)), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, format="JPEG", quality=82, optimize=True, progressive=True)
    return buf.getvalue(), src_w, src_h


def main() -> None:
    ap = argparse.ArgumentParser(description="Thu ảnh minh hoạ cho trang hồ sơ")
    ap.add_argument("--name", default="schiphol")
    # 1100 vừa khít modal rộng 980px trên màn Retina mà không phình file quá đáng.
    ap.add_argument("--max-width", type=int, default=1100)
    # Dưới ngưỡng này coi như không dùng được -> lùi sang ứng viên khác của cùng mục.
    ap.add_argument("--min-width", type=int, default=560,
                    help="bề rộng ảnh GỐC tối thiểu; nhỏ hơn thì thử ứng viên khác")
    ap.add_argument("--inspect", action="store_true",
                    help="kiểm kê ứng viên ảnh theo từng mục (chạy TRƯỚC khi viết CURATION)")
    ap.add_argument("--section", help="chỉ kiểm kê 1 mục: hero|planning|vision|experience")
    args = ap.parse_args()

    if args.inspect:
        inspect_case(args.name, args.section)
        return

    case_dir = ROOT / "raw_data" / "output" / "ws1_airport" / "raw" / args.name
    cur = CURATION.get(args.name)
    if not cur:
        # Không bắt buộc curate tay nữa: tự xếp hạng ứng viên bằng chính score_candidate
        # mà --inspect dùng, rồi lấy ảnh đầu bảng cho mỗi mục. Kém tinh hơn curate tay
        # nhưng khu mới crawl về là có ảnh ngay, không phải chờ ai điền CURATION.
        cur = auto_curation(args.name, case_dir)
        if not cur:
            raise SystemExit(f"'{args.name}': không tìm được ảnh dùng được nào trong trang đã crawl.")
        print(f"  [auto] tự chọn {len(cur)} ảnh (chưa có trong CURATION)")
    pages_dir = case_dir / "pages"
    urls = page_url_map(case_dir)
    out_dir = HERE / "assets" / args.name
    out_dir.mkdir(parents=True, exist_ok=True)

    manifest = {}
    used: dict[str, str] = {}
    for entry in cur:
        # (section, slug, caption) | (…, want) | (…, want, alts) — alts chỉ do
        # auto_curation sinh ra, là danh sách (url, slug) dự phòng xếp theo điểm.
        section, slug, caption = entry[0], entry[1], entry[2]
        want = entry[3] if len(entry) > 3 else None
        alts = entry[4] if len(entry) > 4 else ()
        html_path = pages_dir / f"{slug}.html"
        if not html_path.exists():
            print(f"  [skip] {section}: không thấy {html_path.name}")
            continue
        page_url = urls.get(slug, "")
        img_url = None
        if want:
            # Chọn đúng ảnh đã curate (khớp chuỗi con trong url/alt) — chỉ dựa vào
            # og:image thì hầu như luôn ra ảnh thương hiệu, sai ngữ cảnh mục.
            for c in image_candidates(html_path, page_url):
                if want.lower() in c["url"].lower() or want.lower() in c["alt"].lower():
                    img_url = c["url"]
                    break
            if not img_url:
                print(f"  [warn] {section}: không thấy ảnh khớp '{want}' trong {slug} -> quay về og:image")
        if not img_url:
            img_url = pick_image_url(html_path, page_url)
        if not img_url:
            print(f"  [skip] {section}: trang {slug} không có ảnh")
            continue
        if img_url in used:
            print(f"  [warn] {section}: TRÙNG ảnh với mục '{used[img_url]}' — nên đổi slug/want")
        used[img_url] = section
        # Ảnh đầu bảng hay hỏng vĩnh viễn chứ không phải chập chờn: 403 chặn hotlink,
        # 404 media đã dời, hoặc URL hoá ra là API/map-tile không phải ảnh. Nên khi
        # tải hỏng thì lùi xuống ứng viên kế tiếp của cùng mục, đừng bỏ trống luôn.
        data, last_err, got_url, got_slug = None, None, img_url, slug
        best = None          # ảnh to nhất tìm được dù chưa đạt ngưỡng, dùng khi hết cách
        for cand_url, cand_slug in [(img_url, slug)] + list(alts):
            if cand_url != img_url and cand_url in used:
                continue
            blob = src_w = src_h = None
            for candidate in upsize_variants(cand_url):
                try:
                    # Biến thể xếp từ to xuống nhỏ, nên cái ĐẦU TIÊN tải được đã là bản
                    # lớn nhất còn tồn tại. Thử tiếp chỉ ra ảnh nhỏ hơn — vừa vô ích vừa
                    # tốn thêm 4 request cho mỗi ứng viên bị loại.
                    blob, src_w, src_h = fetch_resize(candidate, args.max_width)
                    break
                except Exception as exc:  # noqa: BLE001
                    last_err = exc
            if blob is None:
                print(f"  [bỏ] {section}: {cand_url[:56]} -> {str(last_err)[:60]}")
                continue

            ratio = src_w / max(src_h, 1)
            if not 0.30 <= ratio <= 3.5:
                # 680x29 hay 102x1200 là thanh trang trí / dải phân cách, không phải
                # ảnh minh hoạ — phóng to cỡ nào cũng vô dụng.
                last_err = f"tỷ lệ {src_w}x{src_h} không phải ảnh minh hoạ"
            elif src_w < HARD_MIN_W or src_w * src_h < HARD_MIN_AREA:
                last_err = f"chỉ {src_w}x{src_h}, quá nhỏ để dùng"
            else:
                if best is None or src_w > best[1]:
                    best = (blob, src_w, cand_url, cand_slug)
                if src_w >= args.min_width:
                    data, got_url, got_slug = blob, cand_url, cand_slug
                else:
                    last_err = f"chỉ {src_w}px, dưới ngưỡng {args.min_width}px"
            if data is not None:
                break
            print(f"  [bỏ] {section}: {cand_url[:56]} -> {str(last_err)[:60]}")
        if data is None and best is not None:
            # Không khu nào có ảnh đạt ngưỡng thì vẫn lấy tấm to nhất, còn hơn để trống.
            data, _, got_url, got_slug = best
            print(f"  [nhỏ] {section}: không ảnh nào đạt {args.min_width}px, dùng bản {best[1]}px")
        if data is None:
            print(f"  [fail] {section}: hết ứng viên -> {last_err}")
            continue
        used[got_url] = section
        fname = f"{section}.jpg"
        (out_dir / fname).write_bytes(data)
        manifest[section] = {"file": fname, "source_image": got_url,
                             "page_url": urls.get(got_slug, ""), "caption": caption,
                             "bytes": len(data)}
        print(f"  [ok] {section}: {len(data):,} bytes <- {got_url[:60]}")

    (out_dir / "images.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[done] {len(manifest)} ảnh -> {out_dir}")


if __name__ == "__main__":
    main()
