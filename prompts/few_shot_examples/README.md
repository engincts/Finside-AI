# Few-Shot Örnek Bankası (Faz 9.5)

Gerçek, yüksek kaliteli BDR parçası + beklenen analiz çıktısı çiftleri burada tutulur.
Sentez (Faz 7) promptuna, risk listesindeki baskın kategorilere göre en fazla 2 örnek
dinamik olarak eklenir. Embedding yok — kategori eşleşmesi yeterli.

## Dizin yapısı

```
few_shot_examples/
├── <kategori_adi>/           # RiskKategorisi enum adının küçük harfi
│   ├── ornek1.json
│   └── ornek2.json
└── _SABLON.json              # şablon (yüklenmez; _ ile başlayanlar atlanır)
```

Geçerli `<kategori_adi>` değerleri (`prompts/schemas.py` `RiskKategorisi`):
`denetci_gorusu_ve_kam`, `dava`, `rehin_ipotek_tri`, `kefalet_teminat`,
`kosullu_yukumluluk`, `kur_ve_doviz_riski`, `likidite_ve_borclanma`, `iliskili_taraf`,
`mevzuat_vergi`, `faaliyet_surekliligi_ve_sonraki_olaylar`, `diger_kalitatif_risk`.

## Dosya formatı (`<kategori>/ornek.json`)

```json
{
  "bdr_parcasi": "BDR dipnotundan alınan gerçek metin parçası ...",
  "beklenen_cikti": {
    "genel_kredi_risk_ozeti": "...",
    "karar_egilimi": "Şartlı Olumlu (Ek Teminat / Kısıtlayıcı Taahhüt-Covenant İle)",
    "analist_gerekce_metni": "...",
    "komite_tavsiyesi_ve_sartlar": ["..."]
  }
}
```

Banka boşken pipeline normal çalışır (`few_shot.ilgili_ornekler` `''` döner).
