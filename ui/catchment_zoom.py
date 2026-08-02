import folium

def add_catchment_zoom(m, grid_layer):

    map_name = m.get_name()
    layer_name = grid_layer.get_name()

    js = f"""
<script>

function focusCatchment(name){{

    var gridLayer = {layer_name};

    var bounds = L.latLngBounds([]);

    var selected = [];

    // Reset all borders
    gridLayer.eachLayer(function(layer){{

        layer.setStyle({{
            color:"#444444",
            weight:0.4
        }});

        if(layer.feature.properties.catchment===name){{

            bounds.extend(layer.getBounds());

            selected.push(layer);

        }}

    }});

    if(bounds.isValid()){{

        {map_name}.fitBounds(bounds,{{
            padding:[30,30],
            maxZoom:9
        }});

    }}

    // Blink animation
    let blinkCount = 0;

    function blink(){{

        const highlight = (blinkCount % 2 === 0);

        selected.forEach(function(layer){{

            layer.setStyle({{

                color: highlight ? "#ff0000" : "#444444",

                weight: highlight ? 3 : 0.4

            }});

        }});

        blinkCount++;

        if(blinkCount < 6){{

            setTimeout(blink,300);

        }}
        else{{

            // Leave highlighted
            selected.forEach(function(layer){{

                layer.setStyle({{

                    color:"#ff0000",

                    weight:2

                }});

            }});

        }}

    }}

    blink();

}}

</script>
"""

    m.get_root().html.add_child(folium.Element(js))