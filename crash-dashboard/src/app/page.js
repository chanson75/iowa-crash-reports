"use client";

import { useEffect, useState } from "react";
import { supabase } from "@/lib/supabaseClient";

export default function HomePage() {
  const [reports, setReports] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filters, setFilters] = useState({
    startDate: "",
    endDate: "",
    county: "",
    reportType: "",
  });

  const fetchReports = async () => {
    setLoading(true);

    let query = supabase.from("reports").select("*").order("crash_date", { ascending: false });

    // Apply date filters if set
    if (filters.startDate) query = query.gte("crash_date", filters.startDate);
    if (filters.endDate) query = query.lte("crash_date", filters.endDate);
    if (filters.county) query = query.ilike("county", `%${filters.county}%`);
    if (filters.reportType) query = query.ilike("report_type", `%${filters.reportType}%`);

    const { data, error } = await query.limit(50);

    if (error) console.error("Error fetching reports:", error);
    else setReports(data);

    setLoading(false);
  };

  useEffect(() => {
    fetchReports();
  }, []);

  const handleFilterChange = (e) => {
    setFilters({ ...filters, [e.target.name]: e.target.value });
  };

  const handleFilterSubmit = (e) => {
    e.preventDefault();
    fetchReports();
  };

  return (
    <main className="min-h-screen bg-gray-100 p-6">
      <h1 className="text-4xl font-bold text-center text-gray-800 mb-8">
        Iowa Crash Reports Dashboard
      </h1>

      {/* Filters */}
      <form
        className="bg-white shadow-md rounded-lg p-6 mb-8 flex flex-col md:flex-row md:items-end md:space-x-6 gap-4"
        onSubmit={handleFilterSubmit}
      >
        <div className="flex flex-col">
          <label className="text-gray-800 font-semibold mb-1">Start Date</label>
          <input
            type="date"
            name="startDate"
            value={filters.startDate}
            onChange={handleFilterChange}
            className="border-gray-300 rounded-md p-2 w-full text-gray-900 bg-white placeholder-gray-400"
          />
        </div>

        <div className="flex flex-col">
          <label className="text-gray-800 font-semibold mb-1">End Date</label>
          <input
            type="date"
            name="endDate"
            value={filters.endDate}
            onChange={handleFilterChange}
            className="border-gray-300 rounded-md p-2 w-full text-gray-900 bg-white placeholder-gray-400"
          />
        </div>

        <div className="flex flex-col">
          <label className="text-gray-800 font-semibold mb-1">County</label>
          <input
            type="text"
            name="county"
            placeholder="Enter County"
            value={filters.county}
            onChange={handleFilterChange}
            className="border-gray-300 rounded-md p-2 w-full text-gray-900 bg-white placeholder-gray-400"
          />
        </div>

        <div className="flex flex-col">
          <label className="text-gray-800 font-semibold mb-1">Report Type</label>
          <input
            type="text"
            name="reportType"
            placeholder="Enter Type"
            value={filters.reportType}
            onChange={handleFilterChange}
            className="border-gray-300 rounded-md p-2 w-full text-gray-900 bg-white placeholder-gray-400"
          />
        </div>

        <div className="flex justify-end md:mt-0 mt-2 md:ml-auto">
          <button
            type="submit"
            className="bg-blue-600 text-white font-semibold px-5 py-2 rounded-md hover:bg-blue-700 transition"
          >
            Apply Filters
          </button>
        </div>
      </form>


      {/* Reports */}
      {loading ? (
        <p className="text-center text-gray-600">Loading reports...</p>
      ) : reports.length === 0 ? (
        <p className="text-center text-gray-600">No reports found.</p>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {reports.map((report) => (
            <div
              key={report.case_number}
              className="bg-white shadow-md rounded-lg p-5 hover:shadow-xl transition"
            >
              <h2 className="text-xl font-semibold text-gray-900 mb-2">
                Case #{report.case_number}
              </h2>
              <p className="text-gray-700">
                <span className="font-semibold">Type:</span>{" "}
                {report.report_type || "N/A"}
              </p>
              <p className="text-gray-700">
                <span className="font-semibold">County:</span>{" "}
                {report.county || "N/A"}
              </p>
              <p className="text-gray-700">
                <span className="font-semibold">Date:</span>{" "}
                {report.crash_date || "N/A"}
              </p>
              <p className="text-gray-700">
                <span className="font-semibold">Time:</span>{" "}
                {report.crash_time || "N/A"}
              </p>
              <p className="text-gray-700 mt-2">
                <span className="font-semibold">Location:</span>{" "}
                {report.location || "N/A"}
              </p>
              <p className="text-gray-700 mt-2">
                <span className="font-semibold">Summary:</span>{" "}
                {report.summary ? (
                  <span className="line-clamp-3">{report.summary}</span>
                ) : (
                  "N/A"
                )}
              </p>
            </div>
          ))}
        </div>
      )}
    </main>
  );
}
