import math

order = [0, 32, 15, 19, 4, 21, 2, 25, 17, 34, 6, 27, 13, 36, 11, 30, 8, 23, 10, 5, 24, 16, 33, 1, 20, 14, 31, 9, 22, 18, 29, 7, 28, 12, 35, 3, 26]

svg_parts = []
svg_parts.append('<svg xmlns="http://www.w3.org/2000/svg" viewBox="-200 -200 400 400" width="400" height="400">')
svg_parts.append('  <!-- Borde exterior doradito -->')
svg_parts.append('  <circle cx="0" cy="0" r="195" fill="#1e293b" stroke="#f59e0b" stroke-width="10" />')

num_pockets = len(order)
angle_per_pocket = 360 / num_pockets

for i, num in enumerate(order):
    if i == 0:
        color = "#10b981" # Green
    elif i % 2 == 1:
        color = "#ef4444" # Red
    else:
        color = "#0f172a" # Black

    # Calcular la cuña (path)
    start_angle = i * angle_per_pocket - (angle_per_pocket / 2) - 90
    end_angle = start_angle + angle_per_pocket
    
    rad_start = math.radians(start_angle)
    rad_end = math.radians(end_angle)
    
    x1 = 180 * math.cos(rad_start)
    y1 = 180 * math.sin(rad_start)
    x2 = 180 * math.cos(rad_end)
    y2 = 180 * math.sin(rad_end)
    
    # Path para la cuña
    svg_parts.append(f'  <path d="M 0 0 L {x1:.2f} {y1:.2f} A 180 180 0 0 1 {x2:.2f} {y2:.2f} Z" fill="{color}" stroke="#334155" stroke-width="1"/>')
    
    # Texto
    text_angle = start_angle + (angle_per_pocket / 2)
    rad_text = math.radians(text_angle)
    tx = 150 * math.cos(rad_text)
    ty = 150 * math.sin(rad_text)
    
    # Rotar el texto para que apunte hacia el centro
    svg_parts.append(f'  <text x="{tx:.2f}" y="{ty:.2f}" fill="#ffffff" font-family="Arial" font-size="14" font-weight="bold" text-anchor="middle" dominant-baseline="middle" transform="rotate({text_angle + 90:.2f}, {tx:.2f}, {ty:.2f})">{num}</text>')

# Circulo interior de la ruleta (el spinner central)
svg_parts.append('  <circle cx="0" cy="0" r="110" fill="#334155" stroke="#f59e0b" stroke-width="4" />')
svg_parts.append('  <circle cx="0" cy="0" r="90" fill="#0f172a" />')
svg_parts.append('  <!-- Estrella/Cruz central -->')
for j in range(4):
    svg_parts.append(f'  <line x1="0" y1="-90" x2="0" y2="90" stroke="#475569" stroke-width="4" transform="rotate({j*45})" />')
svg_parts.append('  <circle cx="0" cy="0" r="20" fill="#f59e0b" />')

svg_parts.append('</svg>')

with open(r'c:\Proyectos\co\frontend\public\roulette-wheel.svg', 'w') as f:
    f.write("\n".join(svg_parts))

print("SVG Generado exitosamente.")
