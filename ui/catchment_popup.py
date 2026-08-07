import json
import folium


def generate_summary(avg, max_rain):
    """Generate automatic rainfall summary."""

    if max_rain >= 204.5:
        return ("Localized extremely heavy rainfall is expected within the "
                "catchment, while the remaining area is forecast to receive "
                "light to moderate rainfall.")

    elif avg >= 64.5:
        return ("Heavy rainfall is expected across most of the catchment.")

    elif avg >= 15.6:
        return ("Moderate rainfall is expected over the catchment.")

    else:
        return ("Light rainfall is expected over most of the catchment.")


def add_catchment_popup(m, catchment_alert_summary):

    summary_dict = {}

    for _, row in catchment_alert_summary.iterrows():

        summary_dict[row["catchment"]] = {
            "avg": round(row["avg_rain_24h"], 1),
            "max": round(row["max_rain_24h"], 1),
            "vol": round(row["volume_24h_mcm"], 2),
            "alert": row["alert"],
            "summary": generate_summary(
                row["avg_rain_24h"],
                row["max_rain_24h"]
            )
        }

    summary_json = json.dumps(summary_dict)

    html = f"""

<style>

#catchmentPopup{{
    display:none;

    position:fixed;

    top:80px;

    right:20px;

    width:350px;

    background:white;

    border-radius:10px;

    box-shadow:0 2px 12px rgba(0,0,0,.4);

    z-index:999999;

    padding:15px;

    font-family:Arial;

    font-size:15px;
}}

#catchmentPopup h3{{
    margin-top:0;
    font-size:20px;
}}

#popupClose{{
    float:right;
    cursor:pointer;
    color:red;
    font-weight:bold;
    font-size:18px;
}}

</style>


<div id="catchmentPopup">

<span id="popupClose"
onclick="document.getElementById('catchmentPopup').style.display='none';">

✖

</span>

<h3 id="popupName"></h3>

<p id="popupAlert"></p>

<hr>

<b>Average Rainfall</b>

<div id="popupAvg"></div>

<br>

<b>Maximum Rainfall</b>

<div id="popupMax"></div>

<br>

<b>Rainfall Volume</b>

<div id="popupVol"></div>

<hr>

<div id="popupSummary"></div>

</div>


<script>

const catchmentSummary = {summary_json};

function openCatchmentPopup(name){{

    let d = catchmentSummary[name];

    if(!d) return;

    document.getElementById("catchmentPopup").style.display="block";

    document.getElementById("popupName").innerHTML=name;

    document.getElementById("popupAlert").innerHTML="<b>"+d.alert+"</b>";

    document.getElementById("popupAvg").innerHTML=d.avg+" mm";

    document.getElementById("popupMax").innerHTML=d.max+" mm";

    document.getElementById("popupVol").innerHTML=d.vol+" MCM";

    document.getElementById("popupSummary").innerHTML=d.summary;

}}

</script>

"""

    m.get_root().html.add_child(folium.Element(html))