import folium

def add_grid_popup(m, grid_layer):

    map_name = m.get_name()
    layer_name = grid_layer.get_name()

    js = f"""
<script>

function buildGridPopup(p){{

    return `

<div style="width:320px;font-family:Arial">

<h3 style="margin-bottom:5px;">📍 Grid Information</h3>

<table style="width:100%;font-size:13px">

<tr><td><b>Catchment</b></td><td>${{p.catchment}}</td></tr>

<tr><td><b>Latitude</b></td><td>${{Number(p.lat_gfs).toFixed(4)}}</td></tr>

<tr><td><b>Longitude</b></td><td>${{Number(p.lon_gfs).toFixed(4)}}</td></tr>

<tr><td><b>Area</b></td><td>${{Number(p.area_km2).toFixed(2)}} km²</td></tr>

</table>

<hr>

<h3 style="margin-bottom:5px;">🌧 Rain Forecast</h3>

<table style="width:100%;font-size:13px">

<tr><td>Next 3 Hours</td><td>${{Number(p.rain_3h).toFixed(1)}} mm</td></tr>

<tr><td>Next 6 Hours</td><td>${{Number(p.rain_6h).toFixed(1)}} mm</td></tr>

<tr><td>Next 12 Hours</td><td>${{Number(p.rain_12h).toFixed(1)}} mm</td></tr>

<tr><td>Next 24 Hours</td><td>${{Number(p.rain_24h).toFixed(1)}} mm</td></tr>

<tr><td>2nd Day 6 Hours</td><td>${{Number(p.rain_2nd_day_6hr).toFixed(1)}} mm</td></tr>

<tr><td>2nd Day 12 Hours</td><td>${{Number(p.rain_2nd_day_12hr).toFixed(1)}} mm</td></tr>

<tr><td>2nd Day 24 Hours</td><td>${{Number(p.rain_2nd_day_24hr).toFixed(1)}} mm</td></tr>

</table>

<hr>

<h3 style="margin-bottom:5px;">💧 Rainfall Volume</h3>

<table style="width:100%;font-size:13px">

<tr><td>3 Hours</td><td>${{Number(p.vol_3h).toFixed(3)}} MCM</td></tr>

<tr><td>6 Hours</td><td>${{Number(p.vol_6h).toFixed(3)}} MCM</td></tr>

<tr><td>12 Hours</td><td>${{Number(p.vol_12h).toFixed(3)}} MCM</td></tr>

<tr><td>24 Hours</td><td>${{Number(p.vol_24h).toFixed(3)}} MCM</td></tr>

<tr><td>2nd Day 6 Hours</td><td>${{Number(p.vol_2nd_day_6hr).toFixed(3)}} MCM</td></tr>

<tr><td>2nd Day 12 Hours</td><td>${{Number(p.vol_2nd_day_12hr).toFixed(3)}} MCM</td></tr>

<tr><td>2nd Day 24 Hours</td><td>${{Number(p.vol_2nd_day_24hr).toFixed(3)}} MCM</td></tr>

</table>

<hr>

<h3 style="margin-bottom:5px;">⚠ Risk Level (24hr based)</h3>

<span style="font-size:16px;font-weight:bold;color:${{p.risk_color}}">

${{p.risk}}

</span>

</div>

`;

}}

window.addEventListener("load", function() {{
    var gridLayer = {layer_name};
    var mapObj = {map_name};

    var popup = L.popup({{
        maxWidth: 350
    }});

    if (gridLayer) {{
        gridLayer.eachLayer(function(layer){{
            layer.on("click", function(e){{
                popup
                    .setLatLng(e.latlng)
                    .setContent(buildGridPopup(layer.feature.properties))
                    .openOn(mapObj);
            }});
        }});
    }}
}});

</script>
"""

    m.get_root().html.add_child(folium.Element(js))