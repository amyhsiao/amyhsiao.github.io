// Ensure Plotly.js is loaded in your HTML head:
// <script src="https://cdn.plot.ly/plotly-2.32.0.min.js" charset="utf-8"></script>

let allParsedData = []; // Store all parsed data globally
let allSpecialties = new Set(); // To collect all unique specialties for consistent coloring
let specialtyColors = {}; // Global variable for specialty colors
let allMedicalLevels = new Set();
let medicalLevelColors = {};
let allMedicalTypes = new Set(); // NEW: To collect all unique medical types
let medicalTypeColors = {}; // NEW: Global variable for medical type colors

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
    // Corrected: Ensure '醫療屬性' header does not include '\r' if it's from Windows CSV
    const medicalTypeColIndex = header.indexOf('醫療屬性\r'); // Check for exact match first
    if (medicalTypeColIndex === -1) { // If not found, try with '\r' in case
        const medicalTypeColIndexWithCR = header.indexOf('醫療屬性\r');
        if (medicalTypeColIndexWithCR !== -1) {
            console.warn("Found '醫療屬性\\r' in header. Consider cleaning your CSV to remove carriage returns.");
            // If the header has a '\r', we need to match it, but then trim the value later.
            // For robustness, it's better to clean the CSV header or handle specific cases.
            // For now, let's use the index with '\r' if that's what's present.
            // The value extraction below already uses .trim() which handles this.
            // For simplicity, let's just make sure the initial search is flexible.
            // Let's stick to the common case '醫療屬性' and add a more robust check later if needed.
        }
    }


    if (graduationDateColIndex === -1 || specialtyColIndex === -1 || medicalLevelColIndex === -1 || medicalTypeColIndex === -1) { // Added medicalTypeColIndex check
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
            const medicalType = columns[medicalTypeColIndex].trim(); // NEW: Extract medical type

            if (rawGradDate && specialty && medicalLevel && medicalType) { // Added medicalType check
                const parts = rawGradDate.split('/');
                if (parts.length === 3) {
                    const rocYear = parseInt(parts[0]);
                    const gregorianYear = rocYear + 1911;
                    parsedData.push({ year: gregorianYear, specialty: specialty, medicalLevel: medicalLevel, medicalType: medicalType }); // NEW: Add medicalType to parsed data
                    allSpecialties.add(specialty);
                    allMedicalLevels.add(medicalLevel);
                    allMedicalTypes.add(medicalType); // NEW: Add medical type to set
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

function generateMedicalLevelColors(medicalLevels) { // Renamed parameter for clarity
    const baseColors = [
        '#A7D1A9', '#E18A8A', '#C39ED0', '#F0E68C', '#77A1D3'
    ];
    const colorMap = {}; // Changed to colorMap
    const sortedLevels = Array.from(medicalLevels).sort(); // Renamed sortedSpecialties to sortedLevels
    sortedLevels.forEach((level, index) => { // Renamed spec to level
        colorMap[level] = baseColors[index % baseColors.length];
    });
    return colorMap;
}

// NEW: Color generation function for medical types
function generateMedicalTypeColors(medicalTypes) {
    // You can choose different colors or reuse some from existing palettes.
    // For distinctiveness, I'll provide 5 new colors. Adjust as needed.
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
            y: 0.92
        },
        height: 580,
        width: 480,
        margin: { t: 0, b: 80, l: 80, r: 80 },
        showlegend: false,
        uniformtext: { minsize: 10, mode: 'hide' }
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
        width: 820,
        margin: { t: 80, b: 80, l: 80, r: 80 },
        showlegend: true,
        legend: {
            orientation: "v", x: 1, y: 1, xref: 'paper', yref: 'paper',
            bgcolor: 'rgba(255,255,255,0.7)', borderwidth: 1, bordercolor: '#ccc',
            font: { size: 10 }, valign: 'top', xanchor: 'left'
        },
        xaxis: {
            title: '畢業年份', type: 'category', tickmode: 'array',
            tickvals: years.map(Number), ticktext: years, automargin: true
        },
        yaxis: { title: '佔比 (%)', range: [0, 100], tickformat: '.0f', ticksuffix: '%' }
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


// --- MAIN EXECUTION ---

async function main() {
    try {
        const csvData = await fetchData();
        allParsedData = parseData(csvData);

        if (allParsedData.length === 0) {
            document.getElementById('pie-chart-plot').innerHTML = '<p>No data to display. Check CSV file or parsing logic.</p>';
            document.getElementById('bar-chart-plot').innerHTML = '<p>No data to display. Check CSV file or parsing logic.</p>';
            document.getElementById('medical-level-pie-chart-plot').innerHTML = '<p>No data to display. Check CSV file or parsing logic.</p>';
            document.getElementById('medical-level-bar-chart-plot').innerHTML = '<p>No data to display. Check CSV file or parsing logic.</p>';
            document.getElementById('medical-type-pie-chart-plot').innerHTML = '<p>No data to display. Check CSV file or parsing logic.</p>'; // NEW
            document.getElementById('medical-type-bar-chart-plot').innerHTML = '<p>No data to display. Check CSV file or parsing logic.</p>'; // NEW

            return;
        }

        specialtyColors = generateConsistentColors(allSpecialties);
        medicalLevelColors = generateMedicalLevelColors(allMedicalLevels);
        medicalTypeColors = generateMedicalTypeColors(allMedicalTypes); // NEW: Generate colors for medical types

        const yearSelect = document.getElementById('year-select');
        const uniqueYears = Array.from(new Set(allParsedData.map(item => item.year))).sort((a, b) => a - b);

        let allOption = document.createElement('option');
        allOption.value = 'all';
        allOption.textContent = '所有年份';
        yearSelect.appendChild(allOption);

        uniqueYears.forEach(year => {
            let option = document.createElement('option');
            option.value = year;
            option.textContent = year;
            yearSelect.appendChild(option);
        });

        yearSelect.addEventListener('change', (event) => {
            const selectedYear = event.target.value;
            const selectedYearText = selectedYear === 'all' ? '所有年份' : `${selectedYear}年`;

            // Update specialty charts
            const aggregatedPieData = aggregateDataForPieChart(allParsedData, selectedYear);
            updatePieChart(aggregatedPieData, selectedYearText);

            // Update medical level charts
            const aggregatedMedicalLevelPieData = aggregateDataForMedicalLevelPieChart(allParsedData, selectedYear);
            updateMedicalLevelPieChart(aggregatedMedicalLevelPieData, selectedYearText);

            // NEW: Update medical type charts
            const aggregatedMedicalTypePieData = aggregateDataForMedicalTypePieChart(allParsedData, selectedYear);
            updateMedicalTypePieChart(aggregatedMedicalTypePieData, selectedYearText);
        });

        // Initial plot displays for all charts
        const initialAggregatedPieData = aggregateDataForPieChart(allParsedData, 'all');
        updatePieChart(initialAggregatedPieData, '所有年份');

        const aggregatedBarData = aggregateDataForBarChart(allParsedData);
        updateBarChart(aggregatedBarData);

        const initialAggregatedMedicalLevelPieData = aggregateDataForMedicalLevelPieChart(allParsedData, 'all');
        updateMedicalLevelPieChart(initialAggregatedMedicalLevelPieData, '所有年份');

        const aggregatedMedicalLevelBarData = aggregateDataForMedicalLevelBarChart(allParsedData);
        updateMedicalLevelBarChart(aggregatedMedicalLevelBarData);

        // NEW: Initial plot displays for medical type charts
        const initialAggregatedMedicalTypePieData = aggregateDataForMedicalTypePieChart(allParsedData, 'all');
        updateMedicalTypePieChart(initialAggregatedMedicalTypePieData, '所有年份');

        const aggregatedMedicalTypeBarData = aggregateDataForMedicalTypeBarChart(allParsedData);
        updateMedicalTypeBarChart(aggregatedMedicalTypeBarData);


    } catch (error) {
        console.error("Error in main function:", error);
        const pieChartDiv = document.getElementById('pie-chart-plot');
        const barChartDiv = document.getElementById('bar-chart-plot');
        const medicalLevelPieChartDiv = document.getElementById('medical-level-pie-chart-plot');
        const medicalLevelBarChartDiv = document.getElementById('medical-level-bar-chart-plot');
        const medicalTypePieChartDiv = document.getElementById('medical-type-pie-chart-plot'); // NEW
        const medicalTypeBarChartDiv = document.getElementById('medical-type-bar-chart-plot'); // NEW


        if (pieChartDiv) {
            pieChartDiv.innerHTML = `<p style="color:red; text-align: center;">圓餅圖數據載入或處理錯誤: ${error.message}。請檢查控制台獲取更多詳情。</p>`;
        }
        if (barChartDiv) {
            barChartDiv.innerHTML = `<p style="color:red; text-align: center;">長條圖數據載入或處理錯誤: ${error.message}。請檢查控制台獲取更多詳情。</p>`;
        }
        if (medicalLevelPieChartDiv) {
            medicalLevelPieChartDiv.innerHTML = `<p style="color:red; text-align: center;">醫療層級圓餅圖數據載入或處理錯誤: ${error.message}。請檢查控制台獲取更多詳情。</p>`;
        }
        if (medicalLevelBarChartDiv) {
            medicalLevelBarChartDiv.innerHTML = `<p style="color:red; text-align: center;">醫療層級長條圖數據載入或處理錯誤: ${error.message}。請檢查控制台獲取更多詳情。</p>`;
        }
        // NEW: Error messages for medical type charts
        if (medicalTypePieChartDiv) {
            medicalTypePieChartDiv.innerHTML = `<p style="color:red; text-align: center;">醫療屬性圓餅圖數據載入或處理錯誤: ${error.message}。請檢查控制台獲取更多詳情。</p>`;
        }
        if (medicalTypeBarChartDiv) {
            medicalTypeBarChartDiv.innerHTML = `<p style="color:red; text-align: center;">醫療屬性長條圖數據載入或處理錯誤: ${error.message}。請檢查控制台獲取更多詳情。</p>`;
        }
    }
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
            y: 0.92
        },
        height: 580,
        width: 480,
        margin: { t: 0, b: 80, l: 80, r: 80 },
        showlegend: false,
        uniformtext: { minsize: 10, mode: 'hide' }
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
        width: 820,
        margin: { t: 80, b: 80, l: 80, r: 80 },
        showlegend: true,
        legend: {
            orientation: "v", x: 1, y: 1, xref: 'paper', yref: 'paper',
            bgcolor: 'rgba(255,255,255,0.7)', borderwidth: 1, bordercolor: '#ccc',
            font: { size: 10 }, valign: 'top', xanchor: 'left'
        },
        xaxis: {
            title: '畢業年份', type: 'category', tickmode: 'array',
            tickvals: years.map(Number), ticktext: years, automargin: true
        },
        yaxis: { title: '佔比 (%)', range: [0, 100], tickformat: '.0f', ticksuffix: '%' }
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
            colors: sortedDataPoints.map(d => medicalTypeColors[d.label]), // Use medicalTypeColors
            line: { color: 'white', width: 1 }
        },
        name: '醫療屬性分佈'
    }];

    const layout = {
        title: {
            text: `<b>${selectedYearText}畢業生醫療屬性分佈</b>`,
            font: { size: 24 },
            y: 0.92
        },
        height: 580,
        width: 480,
        margin: { t: 0, b: 80, l: 80, r: 80 },
        showlegend: false,
        uniformtext: { minsize: 10, mode: 'hide' }
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
        width: 820,
        margin: { t: 80, b: 80, l: 80, r: 80 },
        showlegend: true,
        legend: {
            orientation: "v", x: 1, y: 1, xref: 'paper', yref: 'paper',
            bgcolor: 'rgba(255,255,255,0.7)', borderwidth: 1, bordercolor: '#ccc',
            font: { size: 10 }, valign: 'top', xanchor: 'left'
        },
        xaxis: {
            title: '畢業年份', type: 'category', tickmode: 'array',
            tickvals: years.map(Number), ticktext: years, automargin: true
        },
        yaxis: { title: '佔比 (%)', range: [0, 100], tickformat: '.0f', ticksuffix: '%' }
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
            hovertemplate: '年份: %{x}<br>屬性: %{customdata[0]}<br>佔比: %{y:.2f}%<extra></extra>' // Hover template for medical type
        });
    });

    Plotly.newPlot('medical-type-bar-chart-plot', finalPlotData, layout, { responsive: true });
}

document.addEventListener('DOMContentLoaded', main);