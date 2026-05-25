const fs = require('fs');
fetch('https://basemaps.arcgis.com/arcgis/rest/services/World_Basemap_v2/VectorTileServer/resources/styles/root.json')
  .then(res => res.json())
  .then(style => {
    // Fix relative urls
    if (style.sources && style.sources.esri) {
      style.sources.esri.url = 'https://basemaps.arcgis.com/arcgis/rest/services/World_Basemap_v2/VectorTileServer';
    }
    if (style.sprite) {
      style.sprite = style.sprite.replace('../', 'https://basemaps.arcgis.com/arcgis/rest/services/World_Basemap_v2/VectorTileServer/resources/');
    }
    if (style.glyphs) {
      style.glyphs = style.glyphs.replace('../', 'https://basemaps.arcgis.com/arcgis/rest/services/World_Basemap_v2/VectorTileServer/resources/');
    }

    // Keep only road layers
    style.layers = style.layers.filter(l => l.id.toLowerCase().startsWith('road'));

    // Make them red and visible
    style.layers.forEach(l => {
      if (!l.paint) l.paint = {};
      if (l.paint['line-color']) l.paint['line-color'] = '#FF0000';
      if (l.paint['text-color']) l.paint['text-color'] = '#FF0000';
      if (l.minzoom) l.minzoom = Math.max(0, l.minzoom - 5);
    });

    fs.writeFileSync('frontend/public/roads-style.json', JSON.stringify(style, null, 2));
    console.log('Successfully created roads-style.json');
  });
