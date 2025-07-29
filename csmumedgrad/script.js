// Ensure Plotly.js is loaded in your HTML head:
// <script src="https://cdn.plot.ly/plotly-2.32.0.min.js" charset="utf-8"></script>

let allParsedData = []; // Store all parsed data globally
let allSpecialties = new Set(); // To collect all unique specialties for consistent coloring
let specialtyColors = {}; // Global variable for specialty colors
let allMedicalLevels = new Set();
let medicalLevelColors = {};
let allMedicalTypes = new Set(); // To collect all unique medical types
let medicalTypeColors = {}; // Global variable for medical type colors

async function fetchData() {
    const response = await fetch('./analysis_github.csv'); // Adjust path as needed
    if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
    }
    const data = await response.text();
    return data;
}

function parseData(csvData) {
    const lines = csvData.trim().split('\n');
    const header = lines[0].split(',');
    console.log(header);
    const dataRows = lines.slice(1);

    const graduationDateColIndex = header.indexOf('畢業證書發證日期');
    const specialtyColIndex = header.indexOf('執業科別');
    const medicalLevelColIndex = header.indexOf('醫療層級');
    // More robust way to find '醫療屬性' header by trimming each header cell
    let medicalTypeColIndex = -1;
    for (let i = 0; i < header.length; i++) {
        if (header[i].trim() === '醫療屬性') {
            medicalTypeColIndex = i;
            break;
        }
    }

    if (graduationDateColIndex === -1 || specialtyColIndex === -1 || medicalLevelColIndex === -1 || medicalTypeColIndex === -1) {
        console.error("CSV header missing required columns: '畢業證書發證日期', '執業科別', '醫療層級', or '醫療屬性'");
        return [];
    }

    const parsedData = [];
    dataRows.forEach(line => {
        const columns = line.split(',');
        // Ensure columns array has enough elements before accessing indices
        if (columns.length > Math.max(graduationDateColIndex, specialtyColIndex, medicalLevelColIndex, medicalTypeColIndex)) {
            const rawGradDate = columns[graduationDateColIndex].trim();
            const specialty = columns[specialtyColIndex].trim();
            const medicalLevel = columns[medicalLevelColIndex].trim();
            const medicalType = columns[medicalTypeColIndex].trim(); // Extract medical type

            if (rawGradDate && specialty && medicalLevel && medicalType) {
                const parts = rawGradDate.split('/');
                if (parts.length === 3) {
                    const rocYear = parseInt(parts[0]);
                    const gregorianYear = rocYear + 1911;
                    parsedData.push({ year: gregorianYear, specialty: specialty, medicalLevel: medicalLevel, medicalType: medicalType });
                    allSpecialties.add(specialty);
                    allMedicalLevels.add(medicalLevel);
                    allMedicalTypes.add(medicalType);
                } else {
                    console.warn(`Skipping row due to malformed date: ${rawGradDate} in line: ${line}`);
                }
            }
        } else {
            console.warn(`Skipping row due to insufficient columns: ${line}`);
        }
    });
    return parsedData;
}

function generateConsistentColors(specialties) {
    const baseColors = [
        '#A9A9A9', '#C0C0C0', '#DCDCDC', '#EFEFEF', '#B8B8B8',
        '#D2B48C', '#BC9E82', '#CDAA7C', '#EBC79E', '#F5DEB3',
        '#A2CD9F', '#BCE2B1', '#8FD1A8', '#9ACD32', '#7BBF95',
        '#B0C4DE', '#9CBED9', '#ADD8E6', '#83AFBF', '#5F9EA0',
        '#DDA0DD', '#E6B3D1', '#C3B4D8', '#DDA0DD', '#EEDD82',
        '#AFEEEE', '#F0F8FF', '#C5D8B4', '#E0BBE4', '#9EDCBB',
        '#F7CAC9', '#AEC6CF', '#C9BFE1', '#E4D9B6'
    ];
    const specialtyColorMap = {};
    const sortedSpecialties = Array.from(specialties).sort();
    sortedSpecialties.forEach((spec, index) => {
        specialtyColorMap[spec] = baseColors[index % baseColors.length];
    });
    return specialtyColorMap;
}

function generateMedicalLevelColors(medicalLevels) {
    const baseColors = [
        '#A7D1A9', '#E18A8A', '#C39ED0', '#F0E68C', '#77A1D3'
    ];
    const colorMap = {};
    const sortedLevels = Array.from(medicalLevels).sort();
    sortedLevels.forEach((level, index) => {
        colorMap[level] = baseColors[index % baseColors.length];
    });
    return colorMap;
}

function generateMedicalTypeColors(medicalTypes) {
    const baseColors = [
        '#FF9999', // Light Red/Coral
        '#99CCFF', // Light Blue
        '#99FF99', // Light Green
        '#FFCC99', // Light Orange
        '#CCCCFF'  // Light Purple
    ];
    const colorMap = {};
    const sortedTypes = Array.from(medicalTypes).sort();
    sortedTypes.forEach((type, index) => {
        colorMap[type] = baseColors[index % baseColors.length];
    });
    return colorMap;
}

// --- PIE CHART FUNCTIONS (Existing) ---
function aggregateDataForPieChart(dataToAggregate, selectedYear) {
    const aggregated = {};
    let filteredData = dataToAggregate;

    if (selectedYear !== 'all') {
        filteredData = dataToAggregate.filter(item => item.year === parseInt(selectedYear));
    }

    filteredData.forEach(item => {
        if (!item.specialty) return;
        if (!aggregated[item.specialty]) {
            aggregated[item.specialty] = 0;
        }
        aggregated[item.specialty]++;
    });

    return aggregated;
}

function updatePieChart(aggregatedSpecialties, selectedYearText) {
    document.getElementById('pie-chart-plot').innerHTML = '';

    const specialtyLabels = Object.keys(aggregatedSpecialties);
    const specialtyCounts = Object.values(aggregatedSpecialties);

    const totalCount = specialtyCounts.reduce((sum, count) => sum + count, 0);

    const plotTexts = [];
    const plotTextInfos = [];
    const plotTextPositions = [];

    const rawDataPoints = specialtyLabels.map((label, index) => ({
        label: label,
        value: specialtyCounts[index]
    }));

    const sortedDataPoints = rawDataPoints.sort((a, b) => a.label.localeCompare(b.label, 'zh-Hans-CN', {sensitivity: 'base'}));

    sortedDataPoints.forEach(d => {
        const percentage = (d.value / totalCount) * 100;

        let textinfoValue = 'label+percent';
        let textContent = '';
        let textpositionValue = 'auto';

        if (percentage < 1.0) {
            textinfoValue = 'none';
            textContent = '';
            textpositionValue = 'none';
        } else {
            textContent = d.label;
        }

        plotTextInfos.push(textinfoValue);
        plotTexts.push(textContent);
        plotTextPositions.push(textpositionValue);
    });

    const data = [{
        labels: sortedDataPoints.map(d => d.label),
        values: sortedDataPoints.map(d => d.value),
        type: 'pie',
        hoverinfo: 'label+percent+value',
        textinfo: plotTextInfos,
        textposition: plotTextPositions,
        text: plotTexts,
        insidetextorientation: 'radial',
        marker: {
            colors: sortedDataPoints.map(d => specialtyColors[d.label]),
            line: { color: 'white', width: 1 }
        },
        name: '執業科別分佈'
    }];

    const layout = {
        title: {
            text: `<b>${selectedYearText}畢業生執業科別分佈</b>`,
            font: { size: 24 },
            y: 0.95
        },
        height: 560,
        // width: 480, // Plotly's internal width - CSS handles the container size
        margin: { t: 50, b: 80, l: 80, r: 80 },
        showlegend: false,
        uniformtext: { minsize: 10, mode: 'hide' },
        autosize: true // Crucial for responsiveness
    };

    Plotly.newPlot('pie-chart-plot', data, layout, { responsive: true });
}

// --- BAR CHART FUNCTIONS (Existing) ---
function aggregateDataForBarChart(allData) {
    const dataByYear = {};

    allData.forEach(item => {
        if (!item.year || !item.specialty) return;

        if (!dataByYear[item.year]) {
            dataByYear[item.year] = {};
        }
        if (!dataByYear[item.year][item.specialty]) {
            dataByYear[item.year][item.specialty] = 0;
        }
        dataByYear[item.year][item.specialty]++;
    });

    return dataByYear;
}

function updateBarChart(aggregatedDataByYear) {
    document.getElementById('bar-chart-plot').innerHTML = '';

    const years = Object.keys(aggregatedDataByYear).sort();
    const plotData = [];

    Array.from(allSpecialties).sort().forEach(specialty => {
        const yValues = [];
        const xValues = [];
        const specialtyCustomData = [];

        years.forEach(year => {
            xValues.push(year);
            yValues.push(aggregatedDataByYear[year][specialty] || 0);
            specialtyCustomData.push([specialty]);
        });

        if (yValues.some(v => v > 0)) {
            plotData.push({
                x: xValues,
                y: yValues,
                name: specialty,
                type: 'bar',
                marker: { color: specialtyColors[specialty] },
                customdata: specialtyCustomData,
                hoverinfo: 'x+y'
            });
        }
    });

    const layout = {
        title: {
            text: '<b>各畢業年份執業科別分佈 (百分比)</b>',
            font: { size: 24 }
        },
        barmode: 'stack',
        height: 550,
        // width: 820, // Plotly's internal width
        margin: { t: 50, b: 80, l: 80, r: 80 },
        showlegend: true,
        legend: {
            orientation: "v", x: 1, y: 1, xref: 'paper', yref: 'paper',
            bgcolor: 'rgba(255,255,255,0.7)', borderwidth: 1, bordercolor: '#ccc',
            font: { size: 10 }, valign: 'top', xanchor: 'left'
        },
        xaxis: {
            title: '畢業年份', type: 'category', tickmode: 'array',
            tickvals: years.filter((_, i) => i % 5 === 0).map(Number), // Only every 5th year's value
            ticktext: years.filter((_, i) => i % 5 === 0), 
            automargin: true
        },
        yaxis: { title: '佔比 (%)', range: [0, 100], tickformat: '.0f', ticksuffix: '%' },
        autosize: true // Crucial for responsiveness
    };

    const finalPlotData = [];
    plotData.forEach(trace => {
        const percentages = [];
        trace.y.forEach((count, i) => {
            const year = trace.x[i];
            let totalForYear = 0;
            Object.values(aggregatedDataByYear[year]).forEach(count => { totalForYear += count; });
            percentages.push(totalForYear > 0 ? (count / totalForYear) * 100 : 0);
        });
        finalPlotData.push({
            x: trace.x, y: percentages, name: trace.name, type: 'bar',
            marker: trace.marker, customdata: trace.customdata,
            hovertemplate: '年份: %{x}<br>科別: %{customdata[0]}<br>佔比: %{y:.2f}%<extra></extra>'
        });
    });

    Plotly.newPlot('bar-chart-plot', finalPlotData, layout, { responsive: true });
}

// --- MEDICAL LEVEL PIE CHART FUNCTIONS (Existing) ---
function aggregateDataForMedicalLevelPieChart(dataToAggregate, selectedYear) {
    const aggregated = {};
    let filteredData = dataToAggregate;

    if (selectedYear !== 'all') {
        filteredData = dataToAggregate.filter(item => item.year === parseInt(selectedYear));
    }

    filteredData.forEach(item => {
        if (!item.medicalLevel) return;
        if (!aggregated[item.medicalLevel]) {
            aggregated[item.medicalLevel] = 0;
        }
        aggregated[item.medicalLevel]++;
    });

    return aggregated;
}

function updateMedicalLevelPieChart(aggregatedMedicalLevels, selectedYearText) {
    document.getElementById('medical-level-pie-chart-plot').innerHTML = '';

    const medicalLevelLabels = Object.keys(aggregatedMedicalLevels);
    const medicalLevelCounts = Object.values(aggregatedMedicalLevels);

    const totalCount = medicalLevelCounts.reduce((sum, count) => sum + count, 0);

    const rawDataPoints = medicalLevelLabels.map((label, index) => ({
        label: label,
        value: medicalLevelCounts[index]
    }));

    const sortedDataPoints = rawDataPoints.sort((a, b) => a.label.localeCompare(b.label, 'zh-Hans-CN', {sensitivity: 'base'}));

    const data = [{
        labels: sortedDataPoints.map(d => d.label),
        values: sortedDataPoints.map(d => d.value),
        type: 'pie',
        hoverinfo: 'label+percent+value',
        textinfo: 'label+percent',
        insidetextorientation: 'radial',
        marker: {
            colors: sortedDataPoints.map(d => medicalLevelColors[d.label]),
            line: { color: 'white', width: 1 }
        },
        name: '醫療層級分佈'
    }];

    const layout = {
        title: {
            text: `<b>${selectedYearText}畢業生醫療層級分佈</b>`,
            font: { size: 24 },
            y: 0.95
        },
        height: 580,
        //width: 480, // Plotly's internal width
        margin: { t: 50, b: 80, l: 80, r: 80 },
        showlegend: false,
        uniformtext: { minsize: 10, mode: 'hide' },
        autosize: true // Crucial for responsiveness
    };

    Plotly.newPlot('medical-level-pie-chart-plot', data, layout, { responsive: true });
}

// --- MEDICAL LEVEL BAR CHART FUNCTIONS (Existing) ---
function aggregateDataForMedicalLevelBarChart(allData) {
    const dataByYear = {};

    allData.forEach(item => {
        if (!item.year || !item.medicalLevel) return;

        if (!dataByYear[item.year]) {
            dataByYear[item.year] = {};
        }
        if (!dataByYear[item.year][item.medicalLevel]) {
            dataByYear[item.year][item.medicalLevel] = 0;
        }
        dataByYear[item.year][item.medicalLevel]++;
    });

    return dataByYear;
}

function updateMedicalLevelBarChart(aggregatedDataByYear) {
    document.getElementById('medical-level-bar-chart-plot').innerHTML = '';

    const years = Object.keys(aggregatedDataByYear).sort();
    const plotData = [];

    Array.from(allMedicalLevels).sort().forEach(level => {
        const yValues = [];
        const xValues = [];
        const customData = [];

        years.forEach(year => {
            xValues.push(year);
            yValues.push(aggregatedDataByYear[year][level] || 0);
            customData.push([level]);
        });

        if (yValues.some(v => v > 0)) {
            plotData.push({
                x: xValues,
                y: yValues,
                name: level,
                type: 'bar',
                marker: { color: medicalLevelColors[level] },
                customdata: customData,
                hoverinfo: 'x+y'
            });
        }
    });

    const layout = {
        title: {
            text: '<b>各畢業年份醫療層級分佈 (百分比)</b>',
            font: { size: 24 }
        },
        barmode: 'stack',
        height: 550,
        //width: 820, // Plotly's internal width
        margin: { t: 80, b: 80, l: 80, r: 80 },
        showlegend: true,
        legend: {
            orientation: "v", x: 1, y: 1, xref: 'paper', yref: 'paper',
            bgcolor: 'rgba(255,255,255,0.7)', borderwidth: 1, bordercolor: '#ccc',
            font: { size: 10 }, valign: 'top', xanchor: 'left'
        },
        xaxis: {
            title: '畢業年份', type: 'category', tickmode: 'array',
            tickvals: years.filter((_, i) => i % 5 === 0).map(Number), // Only every 5th year's value
            ticktext: years.filter((_, i) => i % 5 === 0), 
            automargin: true
        },
        yaxis: { title: '佔比 (%)', range: [0, 100], tickformat: '.0f', ticksuffix: '%' },
        autosize: true // Crucial for responsiveness
    };

    const finalPlotData = [];
    plotData.forEach(trace => {
        const percentages = [];
        trace.y.forEach((count, i) => {
            const year = trace.x[i];
            let totalForYear = 0;
            Object.values(aggregatedDataByYear[year]).forEach(count => { totalForYear += count; });
            percentages.push(totalForYear > 0 ? (count / totalForYear) * 100 : 0);
        });
        finalPlotData.push({
            x: trace.x, y: percentages, name: trace.name, type: 'bar',
            marker: trace.marker, customdata: trace.customdata,
            hovertemplate: '年份: %{x}<br>層級: %{customdata[0]}<br>佔比: %{y:.2f}%<extra></extra>'
        });
    });

    Plotly.newPlot('medical-level-bar-chart-plot', finalPlotData, layout, { responsive: true });
}

// --- NEW: MEDICAL TYPE PIE CHART FUNCTIONS ---
function aggregateDataForMedicalTypePieChart(dataToAggregate, selectedYear) {
    const aggregated = {};
    let filteredData = dataToAggregate;

    if (selectedYear !== 'all') {
        filteredData = dataToAggregate.filter(item => item.year === parseInt(selectedYear));
    }

    filteredData.forEach(item => {
        if (!item.medicalType) return;
        if (!aggregated[item.medicalType]) {
            aggregated[item.medicalType] = 0;
        }
        aggregated[item.medicalType]++;
    });

    return aggregated;
}

function updateMedicalTypePieChart(aggregatedMedicalTypes, selectedYearText) {
    document.getElementById('medical-type-pie-chart-plot').innerHTML = '';

    const medicalTypeLabels = Object.keys(aggregatedMedicalTypes);
    const medicalTypeCounts = Object.values(aggregatedMedicalTypes);

    const totalCount = medicalTypeCounts.reduce((sum, count) => sum + count, 0);

    const rawDataPoints = medicalTypeLabels.map((label, index) => ({
        label: label,
        value: medicalTypeCounts[index]
    }));

    const sortedDataPoints = rawDataPoints.sort((a, b) => a.label.localeCompare(b.label, 'zh-Hans-CN', {sensitivity: 'base'}));

    const data = [{
        labels: sortedDataPoints.map(d => d.label),
        values: sortedDataPoints.map(d => d.value),
        type: 'pie',
        hoverinfo: 'label+percent+value',
        textinfo: 'label+percent',
        insidetextorientation: 'radial',
        marker: {
            colors: sortedDataPoints.map(d => medicalTypeColors[d.label]),
            line: { color: 'white', width: 1 }
        },
        name: '醫療屬性分佈'
    }];

    const layout = {
        title: {
            text: `<b>${selectedYearText}畢業生醫療屬性分佈</b>`,
            font: { size: 24 },
            y: 0.95
        },
        height: 560,
        //width: 480, // Plotly's internal width
        margin: { t: 80, b: 80, l: 80, r: 80 },
        showlegend: false,
        uniformtext: { minsize: 10, mode: 'hide' },
        autosize: true // Crucial for responsiveness
    };

    Plotly.newPlot('medical-type-pie-chart-plot', data, layout, { responsive: true });
}

// --- NEW: MEDICAL TYPE BAR CHART FUNCTIONS ---
function aggregateDataForMedicalTypeBarChart(allData) {
    const dataByYear = {};

    allData.forEach(item => {
        if (!item.year || !item.medicalType) return;

        if (!dataByYear[item.year]) {
            dataByYear[item.year] = {};
        }
        if (!dataByYear[item.year][item.medicalType]) {
            dataByYear[item.year][item.medicalType] = 0;
        }
        dataByYear[item.year][item.medicalType]++;
    });

    return dataByYear;
}

function updateMedicalTypeBarChart(aggregatedDataByYear) {
    document.getElementById('medical-type-bar-chart-plot').innerHTML = '';

    const years = Object.keys(aggregatedDataByYear).sort();
    const plotData = [];

    Array.from(allMedicalTypes).sort().forEach(type => { // Iterate through medical types
        const yValues = [];
        const xValues = [];
        const customData = [];

        years.forEach(year => {
            xValues.push(year);
            yValues.push(aggregatedDataByYear[year][type] || 0);
            customData.push([type]); // Use type in customData
        });

        if (yValues.some(v => v > 0)) {
            plotData.push({
                x: xValues,
                y: yValues,
                name: type, // Name is the medical type
                type: 'bar',
                marker: { color: medicalTypeColors[type] }, // Use medicalTypeColors
                customdata: customData,
                hoverinfo: 'x+y'
            });
        }
    });

    const layout = {
        title: {
            text: '<b>各畢業年份醫療屬性分佈 (百分比)</b>', // Title for medical type
            font: { size: 24 }
        },
        barmode: 'stack',
        height: 550,
        //width: 820, // Plotly's internal width
        margin: { t: 80, b: 80, l: 80, r: 80 },
        showlegend: true,
        legend: {
            orientation: "v", x: 1, y: 1, xref: 'paper', yref: 'paper',
            bgcolor: 'rgba(255,255,255,0.7)', borderwidth: 1, bordercolor: '#ccc',
            font: { size: 10 }, valign: 'top', xanchor: 'left'
        },
        xaxis: {
            title: '畢業年份', type: 'category', tickmode: 'array',
            tickvals: years.filter((_, i) => i % 5 === 0).map(Number), // Only every 5th year's value
            ticktext: years.filter((_, i) => i % 5 === 0), 
            automargin: true
        },
        yaxis: { title: '佔比 (%)', range: [0, 100], tickformat: '.0f', ticksuffix: '%' },
        autosize: true // Crucial for responsiveness
    };

    const finalPlotData = [];
    plotData.forEach(trace => {
        const percentages = [];
        trace.y.forEach((count, i) => {
            const year = trace.x[i];
            let totalForYear = 0;
            Object.values(aggregatedDataByYear[year]).forEach(count => { totalForYear += count; });
            percentages.push(totalForYear > 0 ? (count / totalForYear) * 100 : 0);
        });
        finalPlotData.push({
            x: trace.x, y: percentages, name: trace.name, type: 'bar',
            marker: trace.marker, customdata: trace.customdata,
            hovertemplate: '年份: %{x}<br>屬性: %{customdata[0]}<br>佔比: %{y:.2f}%<extra></extra>'
        });
    });

    Plotly.newPlot('medical-type-bar-chart-plot', finalPlotData, layout, { responsive: true });
}

document.addEventListener('DOMContentLoaded', async () => {
    try {
        const csvData = await fetchData();
        allParsedData = parseData(csvData);

        // Populate year dropdown
        const years = [...new Set(allParsedData.map(d => d.year))].sort((a, b) => b - a);
        const yearSelect = document.getElementById('year-select');
        yearSelect.innerHTML = '<option value="all">所有年份</option>'; // Add "All Years" option
        years.forEach(year => {
            const option = document.createElement('option');
            option.value = year;
            option.textContent = year;
            yearSelect.appendChild(option);
        });

        // Generate colors after all specialties/levels/types are collected
        specialtyColors = generateConsistentColors(allSpecialties);
        medicalLevelColors = generateMedicalLevelColors(allMedicalLevels);
        medicalTypeColors = generateMedicalTypeColors(allMedicalTypes);

        // Initial plot updates for the default "All Years" or latest year
        const initialYear = yearSelect.value;
        const initialYearText = initialYear === 'all' ? '所有年份' : `${initialYear}年`;

        const aggregatedSpecialties = aggregateDataForPieChart(allParsedData, initialYear);
        updatePieChart(aggregatedSpecialties, initialYearText);

        const aggregatedMedicalLevels = aggregateDataForMedicalLevelPieChart(allParsedData, initialYear);
        updateMedicalLevelPieChart(aggregatedMedicalLevels, initialYearText);

        const aggregatedMedicalTypes = aggregateDataForMedicalTypePieChart(allParsedData, initialYear);
        updateMedicalTypePieChart(aggregatedMedicalTypes, initialYearText);

        const aggregatedBarDataSpecialty = aggregateDataForBarChart(allParsedData);
        updateBarChart(aggregatedBarDataSpecialty);

        const aggregatedBarDataMedicalLevel = aggregateDataForMedicalLevelBarChart(allParsedData);
        updateMedicalLevelBarChart(aggregatedBarDataMedicalLevel);

        const aggregatedBarDataMedicalType = aggregateDataForMedicalTypeBarChart(allParsedData);
        updateMedicalTypeBarChart(aggregatedBarDataMedicalType);

        // Add event listener for year selection
        yearSelect.addEventListener('change', (event) => {
            const selectedYear = event.target.value;
            const selectedYearText = selectedYear === 'all' ? '所有年份' : `${selectedYear}年`;

            const newAggregatedSpecialties = aggregateDataForPieChart(allParsedData, selectedYear);
            updatePieChart(newAggregatedSpecialties, selectedYearText);

            const newAggregatedMedicalLevels = aggregateDataForMedicalLevelPieChart(allParsedData, selectedYear);
            updateMedicalLevelPieChart(newAggregatedMedicalLevels, selectedYearText);

            const newAggregatedMedicalTypes = aggregateDataForMedicalTypePieChart(allParsedData, selectedYear);
            updateMedicalTypePieChart(newAggregatedMedicalTypes, selectedYearText);
            // Bar charts don't change with year select, as they show all years
        });

        // Add resize listener for Plotly charts
        window.addEventListener('resize', () => {
            // Re-call Plotly.newPlot with current data to trigger redraw and responsiveness
            const currentYear = yearSelect.value;
            const currentYearText = currentYear === 'all' ? '所有年份' : `${currentYear}年`;

            updatePieChart(aggregateDataForPieChart(allParsedData, currentYear), currentYearText);
            updateBarChart(aggregateDataForBarChart(allParsedData));

            updateMedicalLevelPieChart(aggregateDataForMedicalLevelPieChart(allParsedData, currentYear), currentYearText);
            updateMedicalLevelBarChart(aggregateDataForMedicalLevelBarChart(allParsedData));

            updateMedicalTypePieChart(aggregateDataForMedicalTypePieChart(allParsedData, currentYear), currentYearText);
            updateMedicalTypeBarChart(aggregateDataForMedicalTypeBarChart(allParsedData));
        });

    } catch (error) {
        console.error('Error during data fetching or processing:', error);
        // Display a user-friendly error message on the page
        document.getElementById('pie-chart-plot').innerHTML = '<p style="color: red;">載入數據失敗，請檢查 CSV 文件路徑或格式。</p>';
        document.getElementById('bar-chart-plot').innerHTML = '<p style="color: red;">載入數據失敗。</p>';
        document.getElementById('medical-level-pie-chart-plot').innerHTML = '<p style="color: red;">載入數據失敗。</p>';
        document.getElementById('medical-level-bar-chart-plot').innerHTML = '<p style="color: red;">載入數據失敗。</p>';
        document.getElementById('medical-type-pie-chart-plot').innerHTML = '<p style="color: red;">載入數據失敗。</p>';
        document.getElementById('medical-type-bar-chart-plot').innerHTML = '<p style="color: red;">載入數據失敗。</p>';
    }
});