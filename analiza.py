"""Symulacja testu cen biletów z randomizacją całych dni wizyty."""
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent
rng = np.random.default_rng(2026)
rows = []
for block in range(16):
    for weekday in range(7):
        dates = pd.Timestamp('2026-05-04') + pd.to_timedelta(
            np.array([14 * block + weekday, 14 * block + weekday + 7]), unit='D')
        variants = rng.permutation(['Stała', 'Dynamiczna'])
        for date, variant in zip(dates, variants):
            weekend = weekday >= 5
            visits = int(rng.poisson(650 if weekend else 390))
            price = 79 if variant == 'Stała' else (89 if weekend else 69)
            probability = (0.31 if weekend else 0.25) * (price / 79) ** (-0.65 if weekend else -1.15)
            sales = rng.binomial(visits, probability)
            rows.append((date, block, weekday, variant, price, visits, sales))

daily = pd.DataFrame(rows, columns=['data_wizyty','blok','dzien_tygodnia','wariant',
                                    'cena_pln','sesje','bilety'])
daily['przychod_pln'] = daily.cena_pln * daily.bilety
assert daily.data_wizyty.is_unique
assert daily.groupby(['blok','dzien_tygodnia']).wariant.nunique().eq(2).all()
assert daily.bilety.le(daily.sesje).all()
daily.to_csv(ROOT / 'dane_syntetyczne.csv', index=False)

# Porównanie dni z tego samego dnia tygodnia w obrębie dwutygodniowego bloku.
# Bootstrap losuje całe bloki, zachowując ich strukturę i pary dni.
pairs = daily.pivot(index=['blok','dzien_tygodnia'], columns='wariant',
                   values=['przychod_pln','bilety'])
results = []
for metric in ['przychod_pln','bilety']:
    for segment, selected in [
        ('Wszystkie dni', pairs),
        ('Dni robocze', pairs.loc[pairs.index.get_level_values('dzien_tygodnia') < 5]),
        ('Weekend', pairs.loc[pairs.index.get_level_values('dzien_tygodnia') >= 5]),
    ]:
        values = selected[metric]
        delta = values.Dynamiczna - values.Stała
        blocks = delta.groupby(level='blok').mean().to_numpy()
        boot = rng.choice(blocks, size=(10000,len(blocks)), replace=True).mean(axis=1)
        low, high = np.quantile(boot, [0.025,0.975])
        results.append((metric,segment,len(values),values.Stała.mean(),
                        values.Dynamiczna.mean(),delta.mean(),low,high))
report = pd.DataFrame(results, columns=['metryka','segment','liczba_par','stala',
                                       'dynamiczna','roznica','ci_95_dol','ci_95_gora'])
report.to_csv(ROOT / 'wyniki.csv', index=False, float_format='%.4f')
print(report.round(2).to_string(index=False))

plot = report[report.metryka.eq('przychod_pln')]
fig, ax = plt.subplots(figsize=(8.2,3.3))
ax.errorbar(plot.roznica, plot.segment,
            xerr=[plot.roznica-plot.ci_95_dol,plot.ci_95_gora-plot.roznica],
            fmt='o', capsize=5, color='#146d70')
ax.axvline(0,color='#666',linewidth=1)
ax.invert_yaxis()
ax.set(title='Różnica średniego przychodu na dzień wizyty',
       xlabel='Cena dynamiczna − stała (zł) · 95% przedział bootstrap')
ax.spines[['top','right','left']].set_visible(False)
fig.tight_layout()
fig.savefig(ROOT / 'przychod.png',dpi=170)
