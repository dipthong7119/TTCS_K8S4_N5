// SCRUM-231 / SCRUM-85 — Dữ liệu mẫu kiểm tra giao diện.
// Các lỗi được gán sẵn để minh họa, không thay thế logic đối soát backend.
window.FinancialReconciliationData = (() => {
    'use strict';

    const sampleRows = [
        {
            session_id: 'DEMO-85-001',
            date: '2026-10-02',
            station_code: 'DEMO-ST-01',
            charge_point_code: 'DEMO-CP-01',
            energy_kwh: 20,
            expected_vnd: 80000,
            invoiced_vnd: 80000,
            collected_vnd: 80000,
            difference_vnd: 0,
            issues: [],
        },
        {
            session_id: 'DEMO-85-002',
            date: '2026-10-03',
            station_code: 'DEMO-ST-01',
            charge_point_code: 'DEMO-CP-01',
            energy_kwh: 10,
            expected_vnd: 40000,
            invoiced_vnd: null,
            collected_vnd: null,
            difference_vnd: null,
            issues: ['missing_invoice'],
        },
        {
            session_id: 'DEMO-85-003',
            date: '2026-10-04',
            station_code: 'DEMO-ST-01',
            charge_point_code: 'DEMO-CP-02',
            energy_kwh: 15,
            expected_vnd: 60000,
            invoiced_vnd: 60000,
            collected_vnd: null,
            difference_vnd: 0,
            issues: ['missing_ledger'],
        },
        {
            session_id: 'DEMO-85-004',
            date: '2026-10-05',
            station_code: 'DEMO-ST-01',
            charge_point_code: 'DEMO-CP-02',
            energy_kwh: 25,
            expected_vnd: 100000,
            invoiced_vnd: 110000,
            collected_vnd: 110000,
            difference_vnd: 10000,
            issues: ['amount_mismatch'],
        },
        {
            session_id: 'DEMO-85-005',
            date: '2026-10-06',
            station_code: 'DEMO-ST-02',
            charge_point_code: 'DEMO-CP-03',
            energy_kwh: 5,
            expected_vnd: 20000,
            invoiced_vnd: 20000,
            collected_vnd: 20000,
            difference_vnd: 0,
            issues: [],
        },
    ];

    async function getReport({ fromDate, toDate, status = 'all', stationCode = '', chargePointCode = '' }) {
        if (!fromDate || !toDate || fromDate > toDate) {
            throw new Error('Ngày bắt đầu phải nhỏ hơn hoặc bằng ngày kết thúc.');
        }

        const rows = sampleRows.filter(row => {
            const withinPeriod = row.date >= fromDate && row.date <= toDate;
            const matchesStatus = status === 'all'
                || (status === 'review' && row.issues.length > 0)
                || row.issues.includes(status);
            return withinPeriod && matchesStatus
                && (!stationCode || row.station_code === stationCode)
                && (!chargePointCode || row.charge_point_code === chargePointCode);
        });

        // Chỉ cộng các giá trị đã có trong bộ mẫu; null vẫn giữ là dữ liệu thiếu.
        const sum = field => rows.reduce(
            (total, row) => total + (row[field] ?? 0), 0
        );

        return {
            is_sample: true,
            rows: rows.map(row => ({ ...row, issues: [...row.issues] })),
            summary: {
                total_kwh: sum('energy_kwh'),
                total_invoiced_vnd: sum('invoiced_vnd'),
                total_collected_vnd: sum('collected_vnd'),
                // Bộ mẫu dùng tổng trị tuyệt đối để không bù trừ các khoản lệch.
                total_difference_vnd: rows.reduce(
                    (total, row) => total + Math.abs(row.difference_vnd ?? 0), 0
                ),
                review_count: rows.filter(row => row.issues.length > 0).length,
            },
        };
    }

    return {
        getReport,
        getFilterOptions: () => sampleRows.map(row => ({
            stationCode: row.station_code, chargePointCode: row.charge_point_code,
        })),
        defaultPeriod: {
            fromDate: '2026-10-01',
            toDate: '2026-10-31',
        },
    };
})();