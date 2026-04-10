files = [
    'templates/base.html',
    'templates/dashboard.html',
    'templates/tenants.html',
    'templates/properties.html',
    'templates/maintenance.html'
]
replacements = [
    ('ΓÇö', '-'),
    ('ΓÇª', '...'),
    ('Γû╢', '&#9654;'),
    ('ΓÜá∩╕Å', '&#9888;'),
    ('≡ƒôº', '&#128139;'),
    ('≡ƒôè', '&#128202;'),
    ('≡ƒÅá', '&#127968;'),
    ('≡ƒæÑ', '&#128101;'),
    ('≡ƒöº', '&#128295;')
]
for f in files:
    content = open(f, encoding='utf-8', errors='replace').read()
    for old, new in replacements:
        content = content.replace(old, new)
    open(f, 'w', encoding='utf-8').write(content)
    print('Fixed: ' + f)
print('All done!')