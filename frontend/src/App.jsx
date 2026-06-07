import { useState, useEffect } from "react";
import ObsidianLegalGraph from "./components/ObsidianLegalGraph";
import axios from "axios";
import {
  Search,
  Package,
  Cpu,
  Loader2,
  AlertCircle,
  Sparkles,
  Globe,
  Database,
  ChevronDown,
  ChevronUp,
  ArrowLeft,
  Download,
  CheckCircle,
  Brain,
  ShieldCheck,
  X,
  BookOpen,
  FileText,
  CalendarDays,
  UserRound,
  Layers,
  FileUp,
  Settings,
  Plus,
  Trash2,
  ExternalLink,
} from "lucide-react";

const API_BASE_URL = "http://localhost:8000";

function App() {
  const [activeTab, setActiveTab] = useState("valuation");
  const [query, setQuery] = useState("");
  const [products, setProducts] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // AI Valuation state
  const [aiLoading, setAiLoading] = useState(false);
  const [aiResult, setAiResult] = useState(null);
  const [aiError, setAiError] = useState(null);
  const [showRawData, setShowRawData] = useState(false);

  // Approve price state
  const [approving, setApproving] = useState(false);
  const [approveSuccess, setApproveSuccess] = useState(null);
  const [approvedProductData, setApprovedProductData] = useState(null);

  // LLM Wiki customer-facing knowledge profile
  const [knowledgeLoading, setKnowledgeLoading] = useState(false);
  const [knowledgeProfile, setKnowledgeProfile] = useState(null);
  const [knowledgeError, setKnowledgeError] = useState(null);

  // Batch Valuation state
  const [batchLoading, setBatchLoading] = useState(false);

  const handleBatchUpload = async (event) => {
    const file = event.target.files[0];
    if (!file) return;

    setBatchLoading(true);
    const formData = new FormData();
    formData.append("file", file);

    try {
      const response = await axios.post(
        `${API_BASE_URL}/api/v1/valuate/batch`,
        formData,
        {
          responseType: "blob",
        },
      );

      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement("a");
      link.href = url;
      link.setAttribute("download", "ket_qua_dinh_gia.csv");
      document.body.appendChild(link);
      link.click();
      link.remove();
    } catch (err) {
      console.error("Batch valuation error:", err);
      alert("Lỗi khi định giá hàng loạt. Vui lòng kiểm tra lại file CSV.");
    } finally {
      setBatchLoading(false);
      event.target.value = null;
    }
  };

  const searchProducts = async (searchQuery) => {
    if (!searchQuery.trim()) {
      setProducts([]);
      setAiResult(null);
      setAiError(null);
      return;
    }

    setLoading(true);
    setError(null);
    setAiResult(null);
    setAiError(null);

    try {
      const response = await axios.get(`${API_BASE_URL}/products/search`, {
        params: { q: searchQuery },
      });
      setProducts(response.data);
    } catch (err) {
      console.error("Error fetching products:", err);
      setError("Không thể kết nối với server. Vui lòng thử lại sau.");
    } finally {
      setLoading(false);
    }
  };

  const askAI = async () => {
    if (!query.trim()) return;

    setAiLoading(true);
    setAiResult(null);
    setAiError(null);

    try {
      const response = await axios.post(`${API_BASE_URL}/api/v1/valuate`, {
        product_name: query,
      });

      const data = response.data;

      if (data.status === "error") {
        setAiError(data.error || "AI gặp lỗi khi xử lý.");
      } else {
        setAiResult(data);
        setApproveSuccess(null);
      }
    } catch (err) {
      console.error("AI error:", err);
      setAiError("Không thể kết nối với AI. Vui lòng thử lại.");
    } finally {
      setAiLoading(false);
    }
  };

  const approvePrice = async (price, source, specs) => {
    setApproving(true);
    setApproveSuccess(null);

    try {
      const response = await axios.post(`${API_BASE_URL}/products/approve`, {
        name: aiResult?.product || query,
        price: String(price),
        source: source || "N/A",
        specifications: specs || "Theo kết quả AI",
      });

      if (response.data.status === "success") {
        setApproveSuccess(
          "Đã phê duyệt giá, lưu vào cơ sở dữ liệu và đồng bộ kho tri thức.",
        );
        setApprovedProductData({
          ...response.data.data,
          wiki_sync: response.data.wiki_sync,
        });
        searchProducts(query);
      }
    } catch (err) {
      console.error("Lỗi khi phê duyệt giá:", err);
      alert("Có lỗi xảy ra khi phê duyệt giá.");
    } finally {
      setApproving(false);
    }
  };

  const openKnowledgeProfile = async (product) => {
    if (!product?.id) return;

    setKnowledgeLoading(true);
    setKnowledgeProfile(null);
    setKnowledgeError(null);

    try {
      const response = await axios.get(
        `${API_BASE_URL}/wiki/product/${product.id}`,
      );
      setKnowledgeProfile(response.data);
    } catch (err) {
      console.error("Knowledge profile error:", err);
      setKnowledgeError(
        "Chưa tìm thấy hồ sơ tri thức của sản phẩm này. Hãy rebuild LLM Wiki hoặc đồng bộ lại sản phẩm.",
      );
    } finally {
      setKnowledgeLoading(false);
    }
  };

  const closeKnowledgeProfile = () => {
    setKnowledgeLoading(false);
    setKnowledgeProfile(null);
    setKnowledgeError(null);
  };

  // Debounce search
  useEffect(() => {
    const timeOutId = setTimeout(() => {
      searchProducts(query);
    }, 500);

    return () => clearTimeout(timeOutId);
  }, [query]);

  // Nếu đã phê duyệt xong, hiển thị màn hình Chi tiết / In PDF
  if (approvedProductData) {
    const product = approvedProductData;

    return (
      <div className="min-h-screen bg-slate-950 text-slate-50 font-sans p-4 md:p-8 print:bg-white print:text-black print:p-0">
        <div className="max-w-4xl mx-auto mb-8 flex justify-between items-center print:hidden">
          <button
            onClick={() => setApprovedProductData(null)}
            className="flex items-center gap-2 text-slate-400 hover:text-white transition-colors bg-slate-900 px-4 py-2 rounded-xl border border-slate-800"
          >
            <ArrowLeft className="w-5 h-5" /> Quay lại tìm kiếm
          </button>

          <button
            onClick={() => window.print()}
            className="flex items-center gap-2 bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 px-6 py-2.5 rounded-xl font-semibold shadow-lg shadow-blue-500/20 transition-all active:scale-95"
          >
            <Download className="w-5 h-5" /> Lưu PDF / In chứng thư
          </button>
        </div>

        <div className="max-w-4xl mx-auto bg-slate-900 border border-slate-800 rounded-2xl p-8 md:p-12 print:bg-white print:border-none print:shadow-none print:p-8 print:w-[100%] print:max-w-none">
          <div className="text-center mb-10 border-b border-slate-800 pb-8 print:border-gray-300">
            <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-emerald-500/10 text-emerald-400 mb-4 print:text-black print:bg-transparent">
              <CheckCircle className="w-10 h-10" />
            </div>

            <h1 className="text-3xl font-bold text-slate-100 print:text-black mb-2 uppercase tracking-wide">
              Chứng Thư Phê Duyệt Giá
            </h1>

            <p className="text-slate-500 print:text-gray-600 font-mono">
              Số: {product.certificate_number || "N/A"}
            </p>

            {product.wiki_sync && (
              <div className="mt-5 inline-flex items-center gap-2 px-4 py-2 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-300 text-sm print:hidden">
                <Brain className="w-4 h-4" />
                {product.wiki_sync.status === "success"
                  ? "Đã đồng bộ vào kho tri thức định giá"
                  : "Đã lưu database, nhưng cần kiểm tra đồng bộ kho tri thức"}
              </div>
            )}
          </div>

          <div className="space-y-6 text-sm md:text-base">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-2 md:gap-4 border-b border-slate-800/50 pb-6 print:border-gray-300 print:grid-cols-3">
              <div className="text-slate-400 print:text-gray-600 font-medium">
                Tên tài sản:
              </div>
              <div className="md:col-span-2 font-bold text-lg text-slate-100 print:text-black">
                {product.name}
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-2 md:gap-4 border-b border-slate-800/50 pb-6 print:border-gray-300 print:grid-cols-3">
              <div className="text-slate-400 print:text-gray-600 font-medium">
                Loại tài sản:
              </div>
              <div className="md:col-span-2 text-slate-300 print:text-black">
                {product.category || "Tài sản định giá"}
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-2 md:gap-4 border-b border-slate-800/50 pb-6 print:border-gray-300 print:grid-cols-3">
              <div className="text-slate-400 print:text-gray-600 font-medium">
                Đơn vị tính:
              </div>
              <div className="md:col-span-2 text-slate-300 print:text-black">
                {product.unit || "Cái"}
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-2 md:gap-4 border-b border-slate-800/50 pb-6 print:border-gray-300 print:grid-cols-3">
              <div className="text-slate-400 print:text-gray-600 font-medium">
                Thông số kỹ thuật / Căn cứ:
              </div>
              <div className="md:col-span-2 text-slate-300 print:text-black whitespace-pre-wrap">
                {product.specifications || "N/A"}
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-2 md:gap-4 border-b border-slate-800/50 pb-6 print:border-gray-300 print:grid-cols-3">
              <div className="text-slate-400 print:text-gray-600 font-medium">
                Nguồn tham khảo:
              </div>
              <div className="md:col-span-2 text-blue-400 print:text-blue-600 break-words">
                {product.source || "N/A"}
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-2 md:gap-4 border-b border-slate-800/50 pb-6 print:border-gray-300 print:grid-cols-3">
              <div className="text-slate-400 print:text-gray-600 font-medium flex items-center h-full">
                Giá phê duyệt:
              </div>
              <div className="md:col-span-2 text-2xl font-bold text-emerald-400 print:text-black">
                {product.price}{" "}
                {String(product.price).toLowerCase().includes("vnd")
                  ? ""
                  : "VND"}
              </div>
            </div>

            <div className="grid grid-cols-2 gap-8 pt-8 text-center print:pt-16">
              <div className="flex flex-col items-center">
                <p className="font-medium mb-16 text-slate-300 print:text-black">
                  Người yêu cầu
                </p>
                <p className="text-slate-500 print:text-gray-500 italic">
                  (Ký và ghi rõ họ tên)
                </p>
              </div>

              <div className="flex flex-col items-center">
                <p className="mb-2 text-slate-400 print:text-gray-600">
                  Ngày {(product.appraisal_date || "").split("/")[0] || "..."}{" "}
                  tháng {(product.appraisal_date || "").split("/")[1] || "..."}{" "}
                  năm {(product.appraisal_date || "").split("/")[2] || "2026"}
                </p>
                <p className="font-medium mb-16 text-slate-300 print:text-black">
                  Người phê duyệt
                </p>
                <p className="text-slate-500 print:text-gray-500 italic">
                  (Ký và ghi rõ họ tên)
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  }

  const noDbResults = !loading && query && products.length === 0 && !error;
  const showKnowledgeModal =
    knowledgeLoading || knowledgeProfile || knowledgeError;
  const profileItem = knowledgeProfile?.item;

  return (
    <div className="min-h-screen bg-slate-950 text-slate-50 font-sans selection:bg-blue-500/30">
      <nav className="border-b border-slate-800 bg-slate-900/50 backdrop-blur-md sticky top-0 z-40">
        <div className="max-w-6xl mx-auto px-4">
          <div className="flex items-center gap-8 h-16">
            <div className="flex gap-4">
              <button
                onClick={() => setActiveTab("valuation")}
                className={`flex items-center gap-2 px-3 py-2 rounded-lg font-medium transition-colors ${
                  activeTab === "valuation"
                    ? "bg-blue-500/10 text-blue-400"
                    : "text-slate-400 hover:text-slate-200 hover:bg-slate-800/50"
                }`}
              >
                <Search className="w-4 h-4" />
                Định giá
              </button>
              <button
                onClick={() => setActiveTab("wiki")}
                className={`flex items-center gap-2 px-3 py-2 rounded-lg font-medium transition-colors ${
                  activeTab === "wiki"
                    ? "bg-violet-500/10 text-violet-400"
                    : "text-slate-400 hover:text-slate-200 hover:bg-slate-800/50"
                }`}
              >
                <BookOpen className="w-4 h-4" />
                Kho tri thức
              </button>
              <button
                onClick={() => setActiveTab("domains")}
                className={`flex items-center gap-2 px-3 py-2 rounded-lg font-medium transition-colors ${
                  activeTab === "domains"
                    ? "bg-emerald-500/10 text-emerald-400"
                    : "text-slate-400 hover:text-slate-200 hover:bg-slate-800/50"
                }`}
              >
                <Settings className="w-4 h-4" />
                Quản lý Domain
              </button>
            </div>
          </div>
        </div>
      </nav>

      {showKnowledgeModal && (
        <div className="fixed inset-0 z-50 bg-slate-950/80 backdrop-blur-sm px-4 py-8 overflow-y-auto">
          <div className="max-w-4xl mx-auto bg-slate-900 border border-slate-800 rounded-3xl shadow-2xl overflow-hidden">
            <div className="flex items-center justify-between px-6 py-5 border-b border-slate-800">
              <div className="flex items-center gap-3">
                <div className="w-11 h-11 rounded-2xl bg-blue-500/10 text-blue-400 flex items-center justify-center">
                  <Brain className="w-6 h-6" />
                </div>
                <div>
                  <h2 className="text-xl font-bold text-slate-100">
                    Hồ sơ tri thức định giá
                  </h2>
                  <p className="text-sm text-slate-500">
                    Thông tin được đồng bộ từ database sang LLM Wiki Framework
                  </p>
                </div>
              </div>

              <button
                onClick={closeKnowledgeProfile}
                className="w-10 h-10 rounded-xl bg-slate-800 hover:bg-slate-700 flex items-center justify-center text-slate-400 hover:text-white transition"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="p-6">
              {knowledgeLoading && (
                <div className="py-16 text-center">
                  <Loader2 className="w-9 h-9 animate-spin text-blue-400 mx-auto mb-4" />
                  <p className="text-slate-400">Đang tải hồ sơ tri thức...</p>
                </div>
              )}

              {knowledgeError && (
                <div className="flex items-start gap-3 p-4 rounded-2xl bg-red-500/10 border border-red-500/20 text-red-300">
                  <AlertCircle className="w-5 h-5 shrink-0 mt-0.5" />
                  <div>
                    <p className="font-semibold mb-1">
                      Không tải được hồ sơ tri thức
                    </p>
                    <p className="text-sm text-red-300/80">{knowledgeError}</p>
                  </div>
                </div>
              )}

              {profileItem && (
                <div className="space-y-6">
                  <div className="rounded-2xl bg-slate-950/70 border border-slate-800 p-5">
                    <div className="flex flex-wrap items-center gap-2 mb-4">
                      <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-300 text-xs font-medium">
                        <ShieldCheck className="w-3.5 h-3.5" />
                        Đã đồng bộ tri thức
                      </span>

                      <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-blue-500/10 border border-blue-500/20 text-blue-300 text-xs font-medium">
                        <Database className="w-3.5 h-3.5" />
                        ID Database: {profileItem.id}
                      </span>

                      {profileItem.page_path && (
                        <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-slate-800 text-slate-400 text-xs">
                          <FileText className="w-3.5 h-3.5" />
                          {profileItem.page_path}
                        </span>
                      )}
                    </div>

                    <h3 className="text-2xl font-bold text-white mb-2">
                      {profileItem.name}
                    </h3>

                    <p className="text-sm text-slate-400 leading-relaxed">
                      {knowledgeProfile.explanation}
                    </p>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <InfoCard
                      icon={<Database className="w-5 h-5" />}
                      title="Giá thẩm định"
                      value={
                        profileItem.price
                          ? `${profileItem.price} VND`
                          : "Chưa xác định"
                      }
                      highlight
                    />

                    <InfoCard
                      icon={<Layers className="w-5 h-5" />}
                      title="Đơn vị tính"
                      value={profileItem.unit || "Chưa xác định"}
                    />

                    <InfoCard
                      icon={<CalendarDays className="w-5 h-5" />}
                      title="Ngày thẩm định"
                      value={profileItem.appraisal_date || "Chưa xác định"}
                    />

                    <InfoCard
                      icon={<FileText className="w-5 h-5" />}
                      title="Chứng thư"
                      value={profileItem.certificate_number || "Chưa xác định"}
                    />

                    <InfoCard
                      icon={<Globe className="w-5 h-5" />}
                      title="Nguồn dữ liệu"
                      value={profileItem.source || "Chưa xác định"}
                    />

                    <InfoCard
                      icon={<UserRound className="w-5 h-5" />}
                      title="Người thẩm định"
                      value={profileItem.appraiser || "Chưa xác định"}
                    />
                  </div>

                  <div className="rounded-2xl bg-slate-950/70 border border-slate-800 p-5">
                    <div className="flex items-center gap-2 mb-3">
                      <Cpu className="w-5 h-5 text-blue-400" />
                      <h4 className="font-semibold text-slate-100">
                        Thông số kỹ thuật
                      </h4>
                    </div>
                    <p className="text-sm text-slate-400 leading-relaxed whitespace-pre-wrap">
                      {profileItem.specifications ||
                        "Chưa có thông số kỹ thuật."}
                    </p>
                  </div>

                  <div className="rounded-2xl bg-slate-950/70 border border-slate-800 p-5">
                    <div className="flex items-center gap-2 mb-3">
                      <BookOpen className="w-5 h-5 text-violet-400" />
                      <h4 className="font-semibold text-slate-100">
                        Concept nghiệp vụ liên quan
                      </h4>
                    </div>

                    <div className="flex flex-wrap gap-2">
                      {(knowledgeProfile.concepts || []).map((concept) => (
                        <span
                          key={concept.id}
                          className="px-3 py-2 rounded-xl bg-violet-500/10 border border-violet-500/20 text-violet-200 text-sm"
                          title={concept.description}
                        >
                          {concept.title}
                        </span>
                      ))}
                    </div>

                    <p className="text-xs text-slate-500 mt-4 leading-relaxed">
                      Các concept này được dùng để AI Agent hiểu ngữ cảnh định
                      giá, nguồn dữ liệu, căn cứ tham chiếu và khả năng tái sử
                      dụng tri thức cho các lần định giá sau.
                    </p>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {activeTab === "valuation" ? (
        <>
          <header className="relative overflow-hidden pt-16 pb-12 px-4">
            <div className="absolute top-0 left-1/2 -translate-x-1/2 w-full max-w-6xl h-full opacity-20 pointer-events-none">
              <div className="absolute top-[-10%] left-[-10%] w-[40%] h-[40%] bg-blue-600 rounded-full blur-[120px]"></div>
              <div className="absolute bottom-[10%] right-[-5%] w-[30%] h-[30%] bg-indigo-600 rounded-full blur-[100px]"></div>
            </div>

            <div className="relative max-w-4xl mx-auto text-center">
              <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-slate-900 border border-slate-800 text-slate-400 text-sm mb-5">
                <Brain className="w-4 h-4 text-blue-400" />
                Tích hợp kho tri thức định giá nội bộ
              </div>

              <h1 className="text-4xl md:text-6xl font-extrabold tracking-tight mb-4 bg-gradient-to-r from-blue-400 to-indigo-400 bg-clip-text text-transparent">
                Tìm Kiếm & Định Giá Sản Phẩm
              </h1>

              <p className="text-lg text-slate-400 mb-8 max-w-2xl mx-auto">
                Tra cứu dữ liệu nội bộ, hỗ trợ AI định giá sản phẩm mới và tự
                động cập nhật hồ sơ tri thức sau khi phê duyệt.
              </p>

              <div className="relative group max-w-2xl mx-auto">
                <div className="absolute -inset-1 bg-gradient-to-r from-blue-600 to-indigo-600 rounded-2xl blur opacity-25 group-focus-within:opacity-50 transition duration-500"></div>
                <div className="relative flex items-center bg-slate-900 border border-slate-800 rounded-xl overflow-hidden px-4 py-1">
                  <Search className="w-6 h-6 text-slate-500" />
                  <input
                    type="text"
                    placeholder="Nhập tên sản phẩm hoặc thông số kỹ thuật..."
                    className="w-full bg-transparent border-none focus:ring-0 text-slate-100 px-4 py-3 placeholder:text-slate-600 outline-none"
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                  />
                  {loading && (
                    <Loader2 className="w-6 h-6 text-blue-500 animate-spin" />
                  )}
                </div>
              </div>

              <div className="max-w-2xl mx-auto mt-6 text-center animate-in fade-in slide-in-from-bottom-2 duration-500">
                <div className="inline-flex items-center gap-4 bg-slate-900/40 p-2 pr-5 rounded-2xl border border-slate-800/80 backdrop-blur-sm">
                  <label
                    className={`cursor-pointer inline-flex items-center gap-2 px-5 py-2.5 bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 text-white text-sm font-semibold rounded-xl shadow-[0_0_20px_-5px_rgba(16,185,129,0.4)] hover:shadow-[0_0_25px_-5px_rgba(16,185,129,0.6)] transition-all active:scale-95 ${batchLoading ? "opacity-70 pointer-events-none" : ""}`}
                  >
                    <FileUp className="w-4 h-4" />
                    Tải lên CSV định giá
                    <input
                      type="file"
                      accept=".csv"
                      className="hidden"
                      onChange={handleBatchUpload}
                      disabled={batchLoading}
                    />
                  </label>
                  {batchLoading ? (
                    <span className="text-sm text-slate-300 flex items-center gap-2 font-medium">
                      <Loader2 className="w-4 h-4 animate-spin text-emerald-400" />
                      Đang xử lý hàng loạt...
                    </span>
                  ) : (
                    <span className="text-sm text-slate-500 font-medium">
                      Hỗ trợ định giá hàng loạt
                    </span>
                  )}
                </div>
              </div>
            </div>
          </header>

          <main className="max-w-6xl mx-auto px-4 pb-24">
            {error && (
              <div className="flex items-center gap-3 p-4 bg-red-500/10 border border-red-500/20 rounded-xl text-red-400 mb-8">
                <AlertCircle className="w-5 h-5 shrink-0" />
                <p>{error}</p>
              </div>
            )}

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {products.map((product) => (
                <div
                  key={product.id}
                  className="group relative bg-slate-900/50 border border-slate-800 hover:border-blue-500/50 rounded-2xl p-6 transition-all duration-300 hover:-translate-y-1 hover:shadow-[0_20px_40px_-20px_rgba(37,99,235,0.2)]"
                >
                  <div className="flex items-start justify-between mb-4">
                    <div className="flex items-center gap-3">
                      <div className="w-12 h-12 rounded-xl bg-blue-500/10 flex items-center justify-center text-blue-400 group-hover:scale-110 transition-transform duration-300">
                        <Package className="w-6 h-6" />
                      </div>

                      <div>
                        <div className="flex flex-wrap items-center gap-2 mb-1">
                          <span className="inline-flex items-center gap-1 text-xs font-medium text-emerald-400 uppercase tracking-wider">
                            <Database className="w-3 h-3" />
                            Database nội bộ
                          </span>
                          <span className="inline-flex items-center gap-1 text-xs font-medium text-blue-400 uppercase tracking-wider">
                            <Brain className="w-3 h-3" />
                            Hồ sơ tri thức
                          </span>
                        </div>

                        <h3 className="text-xl font-bold text-slate-100 line-clamp-1">
                          {product.name}
                        </h3>
                      </div>
                    </div>

                    <span className="text-xs font-mono text-slate-600">
                      STT: #{product.id}
                    </span>
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mt-4">
                    <div className="space-y-3">
                      <div className="flex items-start gap-2">
                        <Cpu className="w-4 h-4 text-slate-500 shrink-0 mt-0.5" />
                        <div className="text-sm text-slate-400">
                          <span className="text-slate-500 font-medium block">
                            Thông số kỹ thuật:
                          </span>
                          <span className="line-clamp-3">
                            {product.specifications || "N/A"}
                          </span>
                        </div>
                      </div>

                      <div className="text-sm text-slate-400">
                        <span className="text-slate-500 font-medium">
                          Đơn vị tính:{" "}
                        </span>
                        {product.unit || "N/A"}
                      </div>
                    </div>

                    <div className="space-y-3 border-l border-slate-800/50 pl-4">
                      <div className="text-sm">
                        <span className="text-slate-500 font-medium block">
                          Giá thẩm định:
                        </span>
                        <span className="text-blue-400 font-bold text-lg">
                          {product.price ? `${product.price} VND` : "Liên hệ"}
                        </span>
                      </div>

                      <div className="text-xs text-slate-500 space-y-1">
                        <p>
                          <span className="font-medium">Số chứng thư:</span>{" "}
                          {product.certificate_number || "N/A"}
                        </p>
                        <p>
                          <span className="font-medium">Ngày thẩm định:</span>{" "}
                          {product.appraisal_date || "N/A"}
                        </p>
                      </div>
                    </div>
                  </div>

                  <div className="mt-4 pt-4 border-t border-slate-800/50 space-y-3">
                    <div className="flex flex-wrap justify-between items-center gap-2">
                      <div className="text-xs text-slate-500">
                        <span className="font-medium text-slate-600">
                          Nguồn:
                        </span>{" "}
                        {product.source || "N/A"}
                      </div>

                      <div className="text-xs text-slate-500">
                        <span className="font-medium text-slate-600">
                          Người thẩm định:
                        </span>{" "}
                        {product.appraiser || "N/A"}
                      </div>
                    </div>

                    <button
                      onClick={() => openKnowledgeProfile(product)}
                      className="w-full inline-flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl bg-slate-800 hover:bg-blue-600 border border-slate-700 hover:border-blue-500 text-slate-300 hover:text-white text-sm font-semibold transition-all"
                    >
                      <Brain className="w-4 h-4" />
                      Xem hồ sơ tri thức
                    </button>
                  </div>

                  <div className="absolute bottom-0 left-0 w-full h-1 bg-gradient-to-r from-blue-600 to-indigo-600 scale-x-0 group-hover:scale-x-100 transition-transform duration-500 origin-left rounded-b-2xl"></div>
                </div>
              ))}
            </div>

            {noDbResults && !aiResult && (
              <div className="text-center py-16 animate-in fade-in duration-500">
                <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-slate-900 border border-slate-800 mb-4">
                  <Package className="w-8 h-8 text-slate-600" />
                </div>

                <p className="text-slate-500 text-lg mb-2">
                  Không tìm thấy{" "}
                  <span className="text-slate-300 font-semibold">
                    "{query}"
                  </span>{" "}
                  trong Database nội bộ.
                </p>

                <p className="text-slate-600 text-sm mb-8">
                  Hãy để AI tìm kiếm thông tin giá cả trên Internet. Sau khi phê
                  duyệt, sản phẩm sẽ được lưu vào database và đồng bộ vào kho
                  tri thức.
                </p>

                <button
                  onClick={askAI}
                  disabled={aiLoading}
                  className="inline-flex items-center gap-3 px-8 py-4 rounded-2xl font-semibold text-white
                bg-gradient-to-r from-violet-600 to-indigo-600 hover:from-violet-500 hover:to-indigo-500
                shadow-[0_0_30px_-5px_rgba(124,58,237,0.5)] hover:shadow-[0_0_40px_-5px_rgba(124,58,237,0.7)]
                transition-all duration-300 disabled:opacity-60 disabled:cursor-not-allowed
                active:scale-95"
                >
                  {aiLoading ? (
                    <>
                      <Loader2 className="w-5 h-5 animate-spin" />
                      AI đang tìm kiếm...
                    </>
                  ) : (
                    <>
                      <Sparkles className="w-5 h-5" />
                      Hỏi AI định giá sản phẩm này
                    </>
                  )}
                </button>
              </div>
            )}

            {aiLoading && (
              <div className="mt-6 p-6 bg-violet-500/5 border border-violet-500/20 rounded-2xl text-center">
                <Loader2 className="w-8 h-8 text-violet-400 animate-spin mx-auto mb-3" />
                <p className="text-violet-300 font-medium">
                  AI đang tìm kiếm thông tin trên Internet...
                </p>
                <p className="text-slate-500 text-sm mt-1">
                  Quá trình này có thể mất 10–30 giây
                </p>
              </div>
            )}

            {aiError && (
              <div className="mt-6 flex items-center gap-3 p-4 bg-red-500/10 border border-red-500/20 rounded-xl text-red-400">
                <AlertCircle className="w-5 h-5 shrink-0" />
                <p>{aiError}</p>
              </div>
            )}

            {aiResult && (
              <div className="mt-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
                <div className="flex items-center gap-2 mb-4">
                  <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-violet-500/10 border border-violet-500/30 text-violet-300 text-xs font-medium">
                    <Globe className="w-3.5 h-3.5" />
                    Kết quả từ AI + Internet
                  </div>

                  <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-slate-800 text-slate-400 text-xs">
                    <Sparkles className="w-3.5 h-3.5 text-amber-400" />
                    AI định giá
                  </div>
                </div>

                <div className="relative bg-slate-900/70 border border-violet-500/30 rounded-2xl overflow-hidden shadow-[0_0_40px_-10px_rgba(124,58,237,0.3)]">
                  <div className="h-1 w-full bg-gradient-to-r from-violet-600 via-indigo-500 to-blue-600"></div>

                  <div className="p-6">
                    <div className="flex items-center gap-3 mb-5">
                      <div className="w-10 h-10 rounded-xl bg-violet-500/10 flex items-center justify-center">
                        <Sparkles className="w-5 h-5 text-violet-400" />
                      </div>

                      <div>
                        <h3 className="font-bold text-slate-100">
                          Kết quả định giá AI
                        </h3>
                        <p className="text-xs text-slate-500">
                          Sản phẩm: {aiResult.product}
                        </p>
                      </div>
                    </div>

                    <div className="prose prose-invert prose-sm max-w-none">
                      {(() => {
                        const result = aiResult.valuation_result;

                        if (!result) return null;

                        if (typeof result === "string") {
                          const urlRegex = /(https?:\/\/[^\s]+)/g;
                          const parts = result.split(urlRegex);

                          return (
                            <div className="bg-slate-800/50 rounded-xl p-5 border border-slate-700/50">
                              <div className="text-slate-200 leading-relaxed whitespace-pre-wrap text-sm">
                                {parts.map((part, index) => {
                                  if (part.match(urlRegex)) {
                                    return (
                                      <a
                                        key={index}
                                        href={part}
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        className="text-blue-400 hover:text-blue-300 underline font-medium"
                                      >
                                        {part}
                                      </a>
                                    );
                                  }

                                  return <span key={index}>{part}</span>;
                                })}
                              </div>
                            </div>
                          );
                        }

                        return (
                          <div className="space-y-6">
                            {/* Removed Giá chốt dự kiến block as per user request */}
                            {result.reference_quotes &&
                              result.reference_quotes.length > 0 && (
                                <div>
                                  <h4 className="text-slate-400 text-sm font-medium mb-3 uppercase tracking-wider">
                                    Các báo giá tham khảo:
                                  </h4>

                                  <div className="grid grid-cols-1 gap-4">
                                    {result.reference_quotes.map(
                                      (quote, idx) => (
                                        <div
                                          key={idx}
                                          className="bg-slate-800/50 rounded-xl p-4 border border-slate-700/50 flex flex-col sm:flex-row gap-4 justify-between"
                                        >
                                          <div className="space-y-2 flex-1">
                                            <p className="text-slate-200 font-medium text-sm">
                                              {quote.description}
                                            </p>

                                            <p className="text-blue-400 font-bold">
                                              {quote.price}{" "}
                                              {String(quote.price)
                                                .toLowerCase()
                                                .includes("vnd")
                                                ? ""
                                                : "VND"}
                                            </p>

                                            {quote.url && (
                                              <a
                                                href={quote.url}
                                                target="_blank"
                                                rel="noopener noreferrer"
                                                className="text-xs text-violet-400 hover:underline inline-flex items-center gap-1"
                                              >
                                                <Globe className="w-3 h-3" />{" "}
                                                Nguồn tham khảo
                                              </a>
                                            )}
                                          </div>

                                          <div className="flex items-center shrink-0">
                                            <button
                                              onClick={() =>
                                                approvePrice(
                                                  quote.price,
                                                  quote.url || "Internet",
                                                  quote.description,
                                                )
                                              }
                                              disabled={approving}
                                              className="px-3 py-1.5 bg-slate-700 hover:bg-slate-600 text-white text-xs font-medium rounded-lg transition-colors flex items-center gap-2"
                                            >
                                              {approving ? (
                                                <Loader2 className="w-3 h-3 animate-spin" />
                                              ) : (
                                                <Database className="w-3 h-3" />
                                              )}
                                              Phê duyệt giá
                                            </button>
                                          </div>
                                        </div>
                                      ),
                                    )}
                                  </div>
                                </div>
                              )}

                            {approveSuccess && (
                              <div className="p-3 bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 rounded-lg text-sm flex items-center gap-2 mt-4">
                                <Brain className="w-4 h-4" />
                                {approveSuccess}
                              </div>
                            )}
                          </div>
                        );
                      })()}
                    </div>

                    {aiResult.raw_data && (
                      <div className="mt-4">
                        <button
                          onClick={() => setShowRawData(!showRawData)}
                          className="flex items-center gap-2 text-xs text-slate-500 hover:text-slate-300 transition-colors"
                        >
                          {showRawData ? (
                            <ChevronUp className="w-4 h-4" />
                          ) : (
                            <ChevronDown className="w-4 h-4" />
                          )}
                          {showRawData ? "Ẩn" : "Xem"} dữ liệu thu thập từ
                          Internet
                        </button>

                        {showRawData && (
                          <div className="mt-3 p-4 bg-slate-950 rounded-xl border border-slate-800 text-xs text-slate-400 font-mono whitespace-pre-wrap max-h-64 overflow-y-auto">
                            {aiResult.raw_data}
                          </div>
                        )}
                      </div>
                    )}

                    <div className="mt-5 flex items-start gap-2 p-3 bg-amber-500/5 border border-amber-500/20 rounded-lg">
                      <AlertCircle className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
                      <p className="text-xs text-amber-300/80">
                        Kết quả AI mang tính tham khảo. Sau khi được phê duyệt,
                        dữ liệu sẽ được lưu vào cơ sở dữ liệu và đồng bộ vào kho
                        tri thức định giá.
                      </p>
                    </div>
                  </div>
                </div>

                <div className="text-center mt-4">
                  <button
                    onClick={askAI}
                    disabled={aiLoading}
                    className="text-sm text-slate-500 hover:text-violet-400 transition-colors flex items-center gap-1.5 mx-auto"
                  >
                    <Sparkles className="w-3.5 h-3.5" />
                    Tìm kiếm lại với AI
                  </button>
                </div>
              </div>
            )}

            {!query && (
              <div className="text-center py-20">
                <div className="inline-flex items-center justify-center w-20 h-20 rounded-full bg-slate-900/50 border border-slate-800 mb-6 text-slate-700">
                  <Search className="w-10 h-10" />
                </div>

                <h2 className="text-2xl font-semibold text-slate-400 mb-2">
                  Bắt đầu tìm kiếm
                </h2>

                <p className="text-slate-500">
                  Hãy nhập tên hoặc thông số sản phẩm bạn muốn tìm vào thanh tìm
                  kiếm bên trên.
                </p>

                <div className="mt-6 flex flex-wrap items-center justify-center gap-4 text-xs text-slate-600">
                  <span className="flex items-center gap-1.5">
                    <Database className="w-3.5 h-3.5 text-emerald-600" />{" "}
                    Database nội bộ
                  </span>
                  <span className="text-slate-700">→</span>
                  <span className="flex items-center gap-1.5">
                    <Globe className="w-3.5 h-3.5 text-violet-600" /> AI +
                    Internet
                  </span>
                  <span className="text-slate-700">→</span>
                  <span className="flex items-center gap-1.5">
                    <Brain className="w-3.5 h-3.5 text-blue-600" /> Kho tri thức
                    định giá
                  </span>
                </div>
              </div>
            )}
          </main>
        </>
      ) : activeTab === "wiki" ? (
        <WikiTab />
      ) : (
        <DomainRegistryTab />
      )}

      <footer className="border-t border-slate-900 py-8 px-4 text-center">
        <p className="text-slate-600 text-sm">
          &copy; 2026 AI Application. Hệ thống tra cứu, định giá và quản lý tri
          thức sản phẩm.
        </p>
      </footer>
    </div>
  );
}

function InfoCard({ icon, title, value, highlight = false }) {
  return (
    <div className="rounded-2xl bg-slate-950/70 border border-slate-800 p-5">
      <div className="flex items-center gap-2 text-slate-500 mb-2">
        {icon}
        <span className="text-sm font-medium">{title}</span>
      </div>

      <p
        className={
          highlight
            ? "text-xl font-bold text-blue-300"
            : "text-slate-200 text-sm leading-relaxed"
        }
      >
        {value}
      </p>
    </div>
  );
}

function WikiTab() {
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState(null);
  const [knowledgeLoading, setKnowledgeLoading] = useState(false);
  const [knowledgeError, setKnowledgeError] = useState(null);
  const [legalDocs, setLegalDocs] = useState([]);
  const [selectedDoc, setSelectedDoc] = useState(null);
  const [showLegalDocs, setShowLegalDocs] = useState(false);
  const [obsidianGraph, setObsidianGraph] = useState(null);
  const [showObsidianGraph, setShowObsidianGraph] = useState(false);
  const [obsidianGraphError, setObsidianGraphError] = useState(null);

  useEffect(() => {
    const loadLegalDocuments = async () => {
      try {
        const response = await axios.get(
          `${API_BASE_URL}/knowledge/legal-documents`,
        );
        setLegalDocs(response.data.documents || []);
      } catch (err) {
        console.error("Load legal documents error:", err);
      }
    };

    const loadObsidianGraph = async () => {
      try {
        const response = await axios.get(
          `${API_BASE_URL}/knowledge/obsidian-legal-graph`,
        );

        if (response.data.status === "success") {
          setObsidianGraph(response.data);
          setObsidianGraphError(null);
        } else {
          setObsidianGraph(null);
          setObsidianGraphError(
            response.data.message || "Không tải được graph Obsidian.",
          );
        }
      } catch (err) {
        console.error("Load Obsidian graph error:", err);
        setObsidianGraph(null);
        setObsidianGraphError("Không kết nối được API graph Obsidian.");
      }
    };

    loadLegalDocuments();
    loadObsidianGraph();
  }, []);

  const askKnowledgeBase = async () => {
    const finalQuestion = question.trim();

    if (!finalQuestion) {
      setKnowledgeError("Vui lòng nhập câu hỏi cần tra cứu.");
      return;
    }

    setKnowledgeLoading(true);
    setKnowledgeError(null);
    setAnswer(null);

    try {
      const response = await axios.post(`${API_BASE_URL}/knowledge/legal-qa`, {
        question: finalQuestion,
      });

      setAnswer(response.data);
    } catch (err) {
      console.error("Knowledge QA error:", err);
      setKnowledgeError(
        "Không thể kết nối tới Kho tri thức. Vui lòng kiểm tra backend.",
      );
    } finally {
      setKnowledgeLoading(false);
    }
  };

  const handleEnterSubmit = (event) => {
    if (event.key === "Enter" && event.ctrlKey) {
      askKnowledgeBase();
    }
  };

  return (
    <div className="max-w-6xl mx-auto px-6 py-12">
      <div className="text-center mb-10">
        <div className="w-16 h-16 rounded-2xl bg-violet-500/10 border border-violet-500/20 flex items-center justify-center mx-auto mb-6">
          <BookOpen className="w-9 h-9 text-violet-400" />
        </div>

        <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-violet-500/10 border border-violet-500/20 text-violet-300 text-sm mb-5">
          <ShieldCheck className="w-4 h-4" />
          Kho tri thức pháp lý & nghiệp vụ nội bộ
        </div>

        <h2 className="text-4xl md:text-5xl font-black text-white mb-4">
          Kho Tri Thức Cho Nhân Viên
        </h2>

        <p className="text-slate-400 text-lg max-w-3xl mx-auto leading-relaxed">
          Hỗ trợ nhân viên mới hiểu luật, chuẩn mực và quy trình định giá. Đồng
          thời giúp nhân viên cũ tra cứu thêm các văn bản và tình huống pháp lý
          liên quan đến nghiệp vụ.
        </p>
      </div>

      <div className="grid md:grid-cols-3 gap-5 mb-8">
        <button
          type="button"
          onClick={() => setShowLegalDocs((current) => !current)}
          className="text-left rounded-2xl bg-slate-900/70 border border-slate-800 hover:border-violet-500/40 hover:bg-violet-500/5 p-6 transition-colors"
        >
          <div className="w-12 h-12 rounded-xl bg-violet-500/10 flex items-center justify-center mb-4">
            <FileText className="w-6 h-6 text-violet-400" />
          </div>
          <h3 className="text-white font-bold text-lg mb-2">
            Luật & chuẩn mực
          </h3>
          <p className="text-slate-400 text-sm leading-relaxed">
            Bấm để xem đầy đủ thông tin từng văn bản đang có trong kho tri thức
            nội bộ.
          </p>
        </button>

        <div className="rounded-2xl bg-slate-900/70 border border-slate-800 p-6">
          <div className="w-12 h-12 rounded-xl bg-emerald-500/10 flex items-center justify-center mb-4">
            <Layers className="w-6 h-6 text-emerald-400" />
          </div>
          <h3 className="text-white font-bold text-lg mb-2">
            Nghiệp vụ định giá
          </h3>
          <p className="text-slate-400 text-sm leading-relaxed">
            Hỏi về quy trình, cách xử lý tình huống, dữ liệu, căn cứ, hồ sơ và
            rủi ro nghiệp vụ khi làm việc.
          </p>
        </div>

        <div className="rounded-2xl bg-slate-900/70 border border-slate-800 p-6">
          <div className="w-12 h-12 rounded-xl bg-blue-500/10 flex items-center justify-center mb-4">
            <Globe className="w-6 h-6 text-blue-400" />
          </div>
          <h3 className="text-white font-bold text-lg mb-2">Tra cứu mở rộng</h3>
          <p className="text-slate-400 text-sm leading-relaxed">
            Khi câu hỏi cần kiểm tra văn bản mới, hiệu lực hoặc luật ngoài phạm
            vi nội bộ, hệ thống sẽ tự tra cứu thêm nguồn ngoài.
          </p>
        </div>
      </div>

      <div className="mb-8 rounded-3xl border border-blue-500/20 bg-slate-900/80 p-6">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <h3 className="text-2xl font-bold text-white mb-2">
              Sơ đồ tri thức pháp lý
            </h3>

            {obsidianGraphError && (
              <p className="text-xs text-red-300 mt-2">{obsidianGraphError}</p>
            )}
          </div>

          <button
            type="button"
            onClick={() => setShowObsidianGraph((current) => !current)}
            className="px-5 py-3 rounded-xl bg-blue-600 hover:bg-blue-500 text-white font-bold transition-colors"
          >
            {showObsidianGraph ? "Ẩn sơ đồ tri thức" : "Xem sơ đồ tri thức"}
          </button>
        </div>
      </div>

      {showObsidianGraph && (
        <div className="mb-8">
          {obsidianGraphError ? (
            <div className="rounded-3xl border border-red-500/20 bg-red-500/10 p-6 text-red-200">
              {obsidianGraphError}
            </div>
          ) : !obsidianGraph ? (
            <div className="rounded-3xl border border-slate-800 bg-slate-900/80 p-6 text-slate-400">
              Đang tải sơ đồ tri thức từ Obsidian...
            </div>
          ) : (
            <ObsidianLegalGraph graph={obsidianGraph} height={720} />
          )}
        </div>
      )}

      {showLegalDocs && (
        <div className="mb-8 rounded-3xl border border-violet-500/20 bg-slate-900/80 overflow-hidden">
          <div className="p-6 border-b border-slate-800">
            <h3 className="text-2xl font-bold text-white mb-2">
              Luật & chuẩn mực trong Kho tri thức
            </h3>
            <p className="text-slate-500 text-sm">
              Chọn một văn bản để xem thông tin chi tiết. Phần này là kho tài
              liệu nội bộ, tách riêng với module định giá sản phẩm.
            </p>
          </div>

          <div className="grid md:grid-cols-2 gap-4 p-6">
            {legalDocs.length === 0 && (
              <div className="text-slate-500">
                Chưa tải được danh sách văn bản. Kiểm tra backend hoặc endpoint
                /knowledge/legal-documents.
              </div>
            )}

            {legalDocs.map((doc) => (
              <button
                key={doc.id}
                type="button"
                onClick={() => setSelectedDoc(doc)}
                className="text-left rounded-2xl border border-slate-800 bg-slate-950/50 hover:border-violet-500/40 hover:bg-violet-500/5 p-4 transition-colors"
              >
                <div className="flex items-start gap-3">
                  <FileText className="w-5 h-5 text-violet-400 mt-1 shrink-0" />
                  <div>
                    <h4 className="text-slate-100 font-bold mb-1">
                      {doc.title}
                    </h4>
                    <p className="text-xs text-slate-500">
                      {doc.type} • {doc.issuer}
                      {doc.effective_date
                        ? ` • Hiệu lực: ${doc.effective_date}`
                        : ""}
                    </p>
                  </div>
                </div>
              </button>
            ))}
          </div>

          {selectedDoc && (
            <div className="mx-6 mb-6 rounded-2xl border border-violet-500/20 bg-violet-500/5 p-6">
              <div className="flex items-start justify-between gap-4 mb-5">
                <div>
                  <h4 className="text-2xl font-bold text-white">
                    {selectedDoc.title}
                  </h4>
                  <p className="text-sm text-slate-500 mt-1">
                    {selectedDoc.type} • {selectedDoc.issuer}
                    {selectedDoc.document_number
                      ? ` • Số hiệu: ${selectedDoc.document_number}`
                      : ""}
                  </p>
                  <p className="text-sm text-slate-500 mt-1">
                    {selectedDoc.issued_date
                      ? `Ban hành: ${selectedDoc.issued_date}`
                      : ""}
                    {selectedDoc.effective_date
                      ? ` • Hiệu lực: ${selectedDoc.effective_date}`
                      : ""}
                  </p>
                </div>

                <button
                  type="button"
                  onClick={() => setSelectedDoc(null)}
                  className="text-slate-500 hover:text-slate-300"
                >
                  Đóng
                </button>
              </div>

              <div className="space-y-5">
                <div>
                  <h5 className="text-violet-300 font-bold mb-2">Tóm tắt</h5>
                  <p className="text-slate-300 leading-relaxed">
                    {selectedDoc.summary}
                  </p>
                </div>

                {selectedDoc.scope && selectedDoc.scope.length > 0 && (
                  <div>
                    <h5 className="text-blue-300 font-bold mb-2">
                      Phạm vi liên quan
                    </h5>
                    <div className="space-y-2">
                      {selectedDoc.scope.map((item, index) => (
                        <div
                          key={index}
                          className="rounded-xl border border-slate-800 bg-slate-950/40 p-3 text-slate-300"
                        >
                          {item}
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {selectedDoc.key_points &&
                  selectedDoc.key_points.length > 0 && (
                    <div>
                      <h5 className="text-emerald-300 font-bold mb-2">
                        Nội dung nhân viên cần nắm
                      </h5>
                      <div className="space-y-2">
                        {selectedDoc.key_points.map((item, index) => (
                          <div
                            key={index}
                            className="flex items-start gap-3 rounded-xl border border-emerald-500/10 bg-emerald-500/5 p-3 text-slate-300"
                          >
                            <span className="w-6 h-6 rounded-full bg-emerald-500/10 text-emerald-300 flex items-center justify-center text-xs font-bold shrink-0">
                              {index + 1}
                            </span>
                            <span>{item}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                {selectedDoc.employee_usage &&
                  selectedDoc.employee_usage.length > 0 && (
                    <div>
                      <h5 className="text-amber-300 font-bold mb-2">
                        Cách áp dụng trong công việc
                      </h5>
                      <div className="space-y-2">
                        {selectedDoc.employee_usage.map((item, index) => (
                          <div
                            key={index}
                            className="rounded-xl border border-amber-500/10 bg-amber-500/5 p-3 text-slate-300"
                          >
                            {item}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                {selectedDoc.caution && (
                  <div className="rounded-xl border border-red-500/10 bg-red-500/5 p-4">
                    <h5 className="text-red-300 font-bold mb-2">Lưu ý</h5>
                    <p className="text-slate-300 leading-relaxed">
                      {selectedDoc.caution}
                    </p>
                  </div>
                )}

                {selectedDoc.source_url && (
                  <a
                    href={selectedDoc.source_url}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex items-center gap-2 text-blue-400 hover:text-blue-300 text-sm"
                  >
                    Mở nguồn văn bản gốc
                  </a>
                )}
              </div>
            </div>
          )}
        </div>
      )}

      <div className="rounded-3xl border border-violet-500/20 bg-slate-900/80 shadow-2xl shadow-violet-500/10 overflow-hidden">
        <div className="p-6 border-b border-slate-800">
          <div className="flex items-center gap-3 mb-4">
            <Brain className="w-6 h-6 text-violet-400" />
            <div>
              <h3 className="text-xl font-bold text-white">Hỏi Kho tri thức</h3>
              <p className="text-sm text-slate-500">
                Nhập câu hỏi về luật, văn bản, quy trình hoặc tình huống nghiệp
                vụ.
              </p>
            </div>
          </div>

          <textarea
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            onKeyDown={handleEnterSubmit}
            placeholder="Ví dụ: Nếu thiếu dữ liệu thị trường thì nhân viên có được tự ước lượng giá không?"
            className="w-full min-h-[130px] rounded-2xl bg-slate-950/70 border border-slate-800 focus:border-violet-500 focus:ring-2 focus:ring-violet-500/20 outline-none text-slate-100 placeholder:text-slate-600 p-4 resize-none"
          />

          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mt-4">
            <p className="text-sm text-slate-500">
              Nhấn Ctrl + Enter để gửi nhanh. Hệ thống sẽ tự quyết định có cần
              tra cứu nguồn ngoài hay không.
            </p>

            <button
              onClick={askKnowledgeBase}
              disabled={knowledgeLoading}
              className="inline-flex items-center justify-center gap-2 px-6 py-3 rounded-xl bg-violet-600 hover:bg-violet-500 disabled:opacity-60 disabled:cursor-not-allowed text-white font-bold transition-all active:scale-95"
            >
              {knowledgeLoading ? (
                <>
                  <Loader2 className="w-5 h-5 animate-spin" />
                  Đang xử lý...
                </>
              ) : (
                <>
                  <Sparkles className="w-5 h-5" />
                  Hỏi kho tri thức
                </>
              )}
            </button>
          </div>
        </div>
      </div>

      {knowledgeError && (
        <div className="mt-6 rounded-2xl border border-red-500/20 bg-red-500/10 p-4 flex items-start gap-3 text-red-300">
          <AlertCircle className="w-5 h-5 mt-0.5" />
          <span>{knowledgeError}</span>
        </div>
      )}

      {answer && (
        <div className="mt-8 rounded-3xl border border-emerald-500/20 bg-slate-900/80 overflow-hidden shadow-2xl shadow-emerald-500/10">
          <div className="p-6 border-b border-slate-800">
            <div className="flex items-center gap-3 mb-2">
              <CheckCircle className="w-6 h-6 text-emerald-400" />
              <h3 className="text-2xl font-bold text-white">
                Kết quả từ Kho tri thức
              </h3>
            </div>

            <p className="text-sm text-slate-500">Câu hỏi: {answer.question}</p>
          </div>

          <div className="p-6 space-y-6">
            <section>
              <h4 className="text-emerald-300 font-bold mb-3">
                Trả lời từ hệ thống
              </h4>

              <div className="rounded-2xl border border-slate-800 bg-slate-950/50 p-5">
                <p className="text-slate-200 leading-8 whitespace-pre-wrap">
                  {answer.answer}
                </p>
              </div>
            </section>

            {answer.sources && answer.sources.length > 0 && (
              <section>
                <h4 className="text-blue-300 font-bold mb-3">
                  Nguồn ngoài đã tra cứu
                </h4>

                <div className="space-y-3">
                  {answer.sources.map((source, index) => (
                    <div
                      key={index}
                      className="rounded-xl bg-slate-950/60 border border-slate-800 p-4"
                    >
                      <div className="text-slate-200 font-semibold mb-1">
                        {source.title}
                      </div>

                      {source.url && (
                        <a
                          href={source.url}
                          target="_blank"
                          rel="noreferrer"
                          className="text-blue-400 hover:text-blue-300 text-sm break-all"
                        >
                          {source.url}
                        </a>
                      )}

                      {source.content && (
                        <p className="text-slate-500 text-sm mt-2">
                          {source.content}
                        </p>
                      )}
                    </div>
                  ))}
                </div>
              </section>
            )}

            <div className="rounded-2xl bg-red-500/5 border border-red-500/10 p-4">
              <div className="flex items-start gap-3 text-red-200">
                <AlertCircle className="w-5 h-5 mt-0.5 shrink-0" />
                <div>
                  <div className="font-bold mb-1">Lưu ý sử dụng</div>
                  <p className="text-sm text-slate-400 leading-relaxed">
                    {answer.note ||
                      "Kho tri thức chỉ hỗ trợ tra cứu nội bộ, không thay thế văn bản pháp luật gốc hoặc quyết định của người có thẩm quyền."}
                  </p>
                </div>
              </div>
            </div>

            {answer.status === "fallback" && (
              <div className="rounded-2xl bg-amber-500/5 border border-amber-500/10 p-4 text-amber-200 text-sm">
                Backend đang trả lời ở chế độ dự phòng. Kiểm tra GROQ_API_KEY
                trong FastAPIApplication/.env để AI trả lời chi tiết theo từng
                câu hỏi.
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function ObsidianLegalGraphPanel({ graph, error }) {
  const [selectedNodeId, setSelectedNodeId] = useState(null);
  const [searchTerm, setSearchTerm] = useState("");

  if (error) {
    return (
      <div className="mb-8 rounded-3xl border border-red-500/20 bg-red-500/10 p-6 text-red-200">
        {error}
      </div>
    );
  }

  if (!graph) {
    return (
      <div className="mb-8 rounded-3xl border border-slate-800 bg-slate-900/80 p-6 text-slate-400">
        Đang tải sơ đồ tri thức từ Obsidian...
      </div>
    );
  }

  const nodes = graph.nodes || [];
  const edges = graph.edges || [];

  const rootNode =
    nodes.find((node) => node.id === graph.root_id) ||
    nodes.find((node) => node.type === "root") ||
    nodes[0];

  const selectedNode =
    nodes.find((node) => node.id === selectedNodeId) || rootNode;

  const getNode = (id) => nodes.find((node) => node.id === id);

  const typeLabel = {
    root: "Trung tâm",
    group: "Nhóm",
    document: "Văn bản",
    topic: "Chủ đề",
    situation: "Tình huống",
    missing: "Thiếu file",
  };

  const nodeStyle = {
    root: {
      fill: "#1d4ed8",
      stroke: "#60a5fa",
      tag: "bg-blue-500/10 text-blue-300 border-blue-500/20",
    },
    group: {
      fill: "#1e293b",
      stroke: "#94a3b8",
      tag: "bg-slate-800 text-slate-300 border-slate-700",
    },
    document: {
      fill: "#4c1d95",
      stroke: "#a78bfa",
      tag: "bg-violet-500/10 text-violet-300 border-violet-500/20",
    },
    topic: {
      fill: "#0f3460",
      stroke: "#60a5fa",
      tag: "bg-blue-500/10 text-blue-300 border-blue-500/20",
    },
    situation: {
      fill: "#064e3b",
      stroke: "#34d399",
      tag: "bg-emerald-500/10 text-emerald-300 border-emerald-500/20",
    },
    missing: {
      fill: "#7f1d1d",
      stroke: "#f87171",
      tag: "bg-red-500/10 text-red-300 border-red-500/20",
    },
  };

  const shortLabel = (label, max = 36) => {
    const text = String(label || "");
    return text.length <= max ? text : text.slice(0, max - 3) + "...";
  };

  const splitLabel = (label) => {
    const text = shortLabel(label, 34);
    const words = text.split(" ");
    const lines = [];
    let currentLine = "";

    words.forEach((word) => {
      const nextLine = currentLine ? `${currentLine} ${word}` : word;

      if (nextLine.length > 18 && currentLine) {
        lines.push(currentLine);
        currentLine = word;
      } else {
        currentLine = nextLine;
      }
    });

    if (currentLine) {
      lines.push(currentLine);
    }

    return lines.slice(0, 2);
  };

  const relatedEdges = selectedNode
    ? edges.filter(
        (edge) =>
          edge.source === selectedNode.id || edge.target === selectedNode.id,
      )
    : [];

  const inboundEdges = relatedEdges.filter(
    (edge) => edge.target === selectedNode?.id,
  );

  const outboundEdges = relatedEdges.filter(
    (edge) => edge.source === selectedNode?.id,
  );

  const uniqueById = (items) => {
    const seen = new Set();

    return items.filter((item) => {
      if (!item || seen.has(item.id)) {
        return false;
      }

      seen.add(item.id);
      return true;
    });
  };

  const leftNodes = uniqueById(
    inboundEdges.map((edge) => getNode(edge.source)).filter(Boolean),
  );

  const rightNodes = uniqueById(
    outboundEdges.map((edge) => getNode(edge.target)).filter(Boolean),
  );

  const graphHeight = Math.max(
    520,
    Math.max(leftNodes.length, rightNodes.length, 1) * 96 + 170,
  );

  const layout = {};

  if (selectedNode) {
    layout[selectedNode.id] = {
      x: 560,
      y: graphHeight / 2,
    };
  }

  const placeColumn = (items, x) => {
    if (items.length === 0) return;

    const startY = graphHeight / 2 - ((items.length - 1) * 96) / 2;

    items.forEach((node, index) => {
      layout[node.id] = {
        x,
        y: startY + index * 96,
      };
    });
  };

  placeColumn(leftNodes, 220);
  placeColumn(rightNodes, 900);

  const filteredNodes = nodes.filter((node) => {
    const keyword = searchTerm.trim().toLowerCase();

    if (!keyword) return true;

    return (
      String(node.label || "")
        .toLowerCase()
        .includes(keyword) ||
      String(node.file_name || "")
        .toLowerCase()
        .includes(keyword)
    );
  });

  const renderEdge = (edge, index) => {
    const sourcePosition = layout[edge.source];
    const targetPosition = layout[edge.target];

    if (!sourcePosition || !targetPosition) return null;

    const isOutgoingFromSelected = edge.source === selectedNode?.id;
    const curveOffset = isOutgoingFromSelected ? 90 : -90;

    const path = `
      M ${sourcePosition.x} ${sourcePosition.y}
      C ${sourcePosition.x + curveOffset} ${sourcePosition.y},
        ${targetPosition.x - curveOffset} ${targetPosition.y},
        ${targetPosition.x} ${targetPosition.y}
    `;

    return (
      <g key={`${edge.source}-${edge.target}-${index}`}>
        <path
          d={path}
          fill="none"
          stroke="#38bdf8"
          strokeWidth="2.4"
          strokeOpacity="0.95"
          markerEnd="url(#arrowActive)"
        />

        <text
          x={(sourcePosition.x + targetPosition.x) / 2}
          y={(sourcePosition.y + targetPosition.y) / 2 - 12}
          textAnchor="middle"
          fill="#7dd3fc"
          fontSize="11"
          fontWeight="700"
        >
          {edge.label || "liên kết"}
        </text>
      </g>
    );
  };

  const renderNode = (node) => {
    const position = layout[node.id];

    if (!position) return null;

    const active = selectedNode?.id === node.id;
    const style = nodeStyle[node.type] || nodeStyle.group;
    const labelLines = splitLabel(node.label);

    const width = active ? 260 : 220;
    const height = active ? 82 : 68;

    return (
      <g
        key={node.id}
        transform={`translate(${position.x}, ${position.y})`}
        onClick={() => setSelectedNodeId(node.id)}
        className="cursor-pointer"
      >
        <rect
          x={-width / 2}
          y={-height / 2}
          width={width}
          height={height}
          rx="18"
          fill={style.fill}
          stroke={active ? "#ffffff" : style.stroke}
          strokeWidth={active ? 3 : 1.8}
          filter={active ? "url(#nodeGlow)" : undefined}
        />

        <text
          y={labelLines.length === 1 ? -2 : -10}
          textAnchor="middle"
          fill="#ffffff"
          fontSize={active ? 15 : 12}
          fontWeight="800"
        >
          {labelLines.map((line, index) => (
            <tspan key={index} x="0" dy={index === 0 ? 0 : 16}>
              {line}
            </tspan>
          ))}
        </text>

        <text
          y={height / 2 - 10}
          textAnchor="middle"
          fill="#cbd5e1"
          fontSize="10"
          opacity="0.85"
        >
          {typeLabel[node.type] || node.type}
        </text>
      </g>
    );
  };

  const renderNodePicker = (node) => {
    const active = selectedNode?.id === node.id;
    const style = nodeStyle[node.type] || nodeStyle.group;

    return (
      <button
        key={node.id}
        type="button"
        onClick={() => setSelectedNodeId(node.id)}
        className={`text-left rounded-xl border p-3 transition-colors ${
          active
            ? "border-white/60 bg-white/10"
            : "border-slate-800 bg-slate-950/50 hover:border-violet-500/40 hover:bg-violet-500/5"
        }`}
      >
        <div className="flex items-center justify-between gap-3">
          <div className="text-slate-100 font-bold text-sm">{node.label}</div>

          <span
            className={`shrink-0 rounded-full border px-2 py-1 text-[10px] ${style.tag}`}
          >
            {typeLabel[node.type] || node.type}
          </span>
        </div>

        <div className="text-xs text-slate-500 mt-1">{node.file_name}</div>
      </button>
    );
  };

  const visibleGraphNodes = [...leftNodes, selectedNode, ...rightNodes].filter(
    Boolean,
  );

  return (
    <div className="mb-8 rounded-3xl border border-blue-500/20 bg-slate-900/80 overflow-hidden shadow-2xl shadow-blue-500/10">
      <div className="p-6 border-b border-slate-800">
        <h3 className="text-2xl font-bold text-white mb-2">
          Sơ đồ tri thức pháp lý
        </h3>

        <p className="text-slate-500 text-sm">
          Chọn một node ở danh sách bên trái. Sơ đồ chỉ hiển thị node đó và các
          node liên kết trực tiếp.
        </p>
      </div>

      <div className="p-6 space-y-6">
        <div className="grid lg:grid-cols-[0.32fr_0.68fr] gap-6">
          <div className="rounded-2xl border border-slate-800 bg-slate-950/50 p-4">
            <h4 className="text-white font-bold mb-3">Chọn node</h4>

            <input
              value={searchTerm}
              onChange={(event) => setSearchTerm(event.target.value)}
              placeholder="Tìm luật, chủ đề, tình huống..."
              className="w-full mb-4 rounded-xl bg-slate-900 border border-slate-800 px-3 py-2 text-sm text-slate-100 placeholder:text-slate-600 outline-none focus:border-violet-500"
            />

            <div className="space-y-2 max-h-[540px] overflow-y-auto pr-1">
              {filteredNodes.map(renderNodePicker)}
            </div>
          </div>

          <div className="rounded-2xl border border-slate-800 bg-slate-950/60 overflow-x-auto">
            <svg
              viewBox={`0 0 1120 ${graphHeight}`}
              className="min-w-[980px] w-full"
              style={{ height: graphHeight }}
            >
              <defs>
                <marker
                  id="arrowActive"
                  markerWidth="9"
                  markerHeight="9"
                  refX="9"
                  refY="4.5"
                  orient="auto"
                  markerUnits="strokeWidth"
                >
                  <path d="M0,0 L9,4.5 L0,9 Z" fill="#38bdf8" />
                </marker>

                <filter
                  id="nodeGlow"
                  x="-40%"
                  y="-40%"
                  width="180%"
                  height="180%"
                >
                  <feDropShadow
                    dx="0"
                    dy="0"
                    stdDeviation="5"
                    floodColor="#a78bfa"
                    floodOpacity="0.75"
                  />
                </filter>
              </defs>

              <text
                x="220"
                y="35"
                textAnchor="middle"
                fill="#94a3b8"
                fontSize="13"
                fontWeight="700"
              >
                Node trỏ tới node đang chọn
              </text>

              <text
                x="560"
                y="35"
                textAnchor="middle"
                fill="#ffffff"
                fontSize="14"
                fontWeight="800"
              >
                Node đang chọn
              </text>

              <text
                x="900"
                y="35"
                textAnchor="middle"
                fill="#94a3b8"
                fontSize="13"
                fontWeight="700"
              >
                Node được node đang chọn liên kết tới
              </text>

              {relatedEdges.map(renderEdge)}
              {visibleGraphNodes.map(renderNode)}
            </svg>
          </div>
        </div>

        <div className="rounded-3xl border border-violet-500/20 bg-slate-950/60 overflow-hidden">
          <div className="p-5 border-b border-slate-800">
            <div className="text-xs uppercase tracking-wider text-violet-300 font-bold mb-2">
              Giải thích node đang chọn
            </div>

            <h4 className="text-2xl font-bold text-white">
              {selectedNode?.label || "Chưa chọn node"}
            </h4>
          </div>

          <div className="p-5 space-y-5">
            <div>
              <h5 className="text-emerald-300 font-bold mb-2">
                Nội dung đầy đủ
              </h5>

              <div className="rounded-2xl border border-slate-800 bg-slate-900/70 p-5">
                <pre className="whitespace-pre-wrap text-sm text-slate-300 leading-7 font-sans">
                  {selectedNode?.content ||
                    selectedNode?.summary ||
                    "Node này chưa có nội dung."}
                </pre>
              </div>
            </div>

            <div>
              <h5 className="text-blue-300 font-bold mb-3">
                Node liên kết trực tiếp
              </h5>

              {relatedEdges.length === 0 && (
                <div className="rounded-xl border border-slate-800 bg-slate-900/70 p-4 text-slate-500">
                  Node này chưa có liên kết trực tiếp.
                </div>
              )}

              <div className="space-y-3">
                {relatedEdges.map((edge, index) => {
                  const source = getNode(edge.source);
                  const target = getNode(edge.target);

                  return (
                    <div
                      key={`${edge.source}-${edge.target}-${index}`}
                      className="rounded-xl border border-slate-800 bg-slate-900/70 p-4"
                    >
                      <div className="text-slate-300 text-sm">
                        <span className="text-blue-300 font-semibold">
                          {source?.label || edge.source}
                        </span>
                        <span className="text-slate-500 mx-2">
                          — {edge.label || "liên kết"} →
                        </span>
                        <span className="text-emerald-300 font-semibold">
                          {target?.label || edge.target}
                        </span>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            <div className="rounded-2xl border border-amber-500/10 bg-amber-500/5 p-4 text-sm text-slate-400">
              Khi sửa liên kết [[...]] trong Obsidian và refresh lại trang, sơ
              đồ trên FE sẽ thay đổi theo. Phần này chỉ thuộc module Kho tri
              thức, không ảnh hưởng đến Định giá.
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function DomainRegistryTab() {
  const [categories, setCategories] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [expandedCat, setExpandedCat] = useState(null);
  const [newDomain, setNewDomain] = useState("");
  const [showAddCategory, setShowAddCategory] = useState(false);
  const [newCatKey, setNewCatKey] = useState("");
  const [newCatLabel, setNewCatLabel] = useState("");
  const [newCatDomains, setNewCatDomains] = useState("");
  const [actionLoading, setActionLoading] = useState(false);

  const fetchCategories = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await axios.get(`${API_BASE_URL}/api/v1/domains/`);
      setCategories(res.data.categories || []);
    } catch (e) {
      setError("Không thể tải danh sách domain.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchCategories(); }, []);

  const handleAddDomain = async (catKey) => {
    if (!newDomain.trim()) return;
    setActionLoading(true);
    try {
      await axios.post(`${API_BASE_URL}/api/v1/domains/${catKey}/domains`, { domain: newDomain.trim() });
      setNewDomain("");
      fetchCategories();
    } catch (e) {
      alert(e.response?.data?.detail || "Lỗi khi thêm domain.");
    } finally {
      setActionLoading(false);
    }
  };

  const handleRemoveDomain = async (catKey, domain) => {
    if (!confirm(`Xóa domain "${domain}" khỏi danh mục?`)) return;
    setActionLoading(true);
    try {
      await axios.delete(`${API_BASE_URL}/api/v1/domains/${catKey}/domains`, { data: { domain } });
      fetchCategories();
    } catch (e) {
      alert(e.response?.data?.detail || "Lỗi khi xóa domain.");
    } finally {
      setActionLoading(false);
    }
  };

  const handleAddCategory = async () => {
    if (!newCatKey.trim() || !newCatLabel.trim()) return;
    setActionLoading(true);
    try {
      const domains = newCatDomains.split(/[,\n]/).map(d => d.trim()).filter(Boolean);
      await axios.post(`${API_BASE_URL}/api/v1/domains/`, { key: newCatKey.trim(), label: newCatLabel.trim(), domains });
      setNewCatKey(""); setNewCatLabel(""); setNewCatDomains(""); setShowAddCategory(false);
      fetchCategories();
    } catch (e) {
      alert(e.response?.data?.detail || "Lỗi khi tạo danh mục.");
    } finally {
      setActionLoading(false);
    }
  };

  const handleDeleteCategory = async (catKey) => {
    if (!confirm(`Xóa toàn bộ danh mục "${catKey}"?`)) return;
    setActionLoading(true);
    try {
      await axios.delete(`${API_BASE_URL}/api/v1/domains/${catKey}`);
      if (expandedCat === catKey) setExpandedCat(null);
      fetchCategories();
    } catch (e) {
      alert(e.response?.data?.detail || "Lỗi khi xóa danh mục.");
    } finally {
      setActionLoading(false);
    }
  };

  return (
    <div className="max-w-5xl mx-auto px-4 py-12">
      <div className="text-center mb-10">
        <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-emerald-500/10 text-emerald-400 mb-6">
          <Globe className="w-8 h-8" />
        </div>
        <h2 className="text-4xl font-bold text-white mb-4">Quản Lý Domain Tìm Kiếm</h2>
        <p className="text-slate-400 max-w-2xl mx-auto text-lg">
          Cấu hình các domain ưu tiên cho từng danh mục sản phẩm. Tavily sẽ tập trung tìm kiếm giá trên các trang này.
        </p>
      </div>

      {error && (
        <div className="flex items-center gap-3 p-4 bg-red-500/10 border border-red-500/20 rounded-xl text-red-400 mb-6">
          <AlertCircle className="w-5 h-5 shrink-0" /> <p>{error}</p>
        </div>
      )}

      <div className="mb-6 flex justify-end">
        <button
          onClick={() => setShowAddCategory(!showAddCategory)}
          className="inline-flex items-center gap-2 px-5 py-2.5 bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 text-white text-sm font-semibold rounded-xl shadow-lg shadow-emerald-500/20 transition-all active:scale-95"
        >
          <Plus className="w-4 h-4" /> Thêm danh mục mới
        </button>
      </div>

      {showAddCategory && (
        <div className="bg-slate-900 border border-emerald-500/30 rounded-2xl p-6 mb-6 animate-in fade-in slide-in-from-top-2 duration-300">
          <h3 className="text-lg font-bold text-slate-100 mb-4">Tạo danh mục mới</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
            <div>
              <label className="block text-sm text-slate-400 mb-1">Key (viết thường, không dấu)</label>
              <input type="text" value={newCatKey} onChange={e => setNewCatKey(e.target.value)} placeholder="vd: car, appliance" className="w-full bg-slate-800 border border-slate-700 rounded-xl px-4 py-2.5 text-slate-100 placeholder:text-slate-600 outline-none focus:border-emerald-500 transition" />
            </div>
            <div>
              <label className="block text-sm text-slate-400 mb-1">Tên hiển thị</label>
              <input type="text" value={newCatLabel} onChange={e => setNewCatLabel(e.target.value)} placeholder="vd: Ô tô, Đồ gia dụng" className="w-full bg-slate-800 border border-slate-700 rounded-xl px-4 py-2.5 text-slate-100 placeholder:text-slate-600 outline-none focus:border-emerald-500 transition" />
            </div>
          </div>
          <div className="mb-4">
            <label className="block text-sm text-slate-400 mb-1">Danh sách domain (phân cách bằng dấu phẩy hoặc xuống dòng)</label>
            <textarea value={newCatDomains} onChange={e => setNewCatDomains(e.target.value)} rows={3} placeholder="shopee.vn, lazada.vn, tiki.vn" className="w-full bg-slate-800 border border-slate-700 rounded-xl px-4 py-2.5 text-slate-100 placeholder:text-slate-600 outline-none focus:border-emerald-500 transition resize-none" />
          </div>
          <div className="flex gap-3">
            <button onClick={handleAddCategory} disabled={actionLoading} className="px-5 py-2 bg-emerald-600 hover:bg-emerald-500 text-white text-sm font-medium rounded-xl transition-colors">
              {actionLoading ? "Đang tạo..." : "Tạo danh mục"}
            </button>
            <button onClick={() => setShowAddCategory(false)} className="px-5 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 text-sm font-medium rounded-xl transition-colors">Hủy</button>
          </div>
        </div>
      )}

      {loading ? (
        <div className="text-center py-16">
          <Loader2 className="w-8 h-8 text-emerald-400 animate-spin mx-auto mb-3" />
          <p className="text-slate-400">Đang tải danh sách domain...</p>
        </div>
      ) : (
        <div className="space-y-4">
          {categories.map(cat => (
            <div key={cat.key} className="bg-slate-900/70 border border-slate-800 rounded-2xl overflow-hidden hover:border-emerald-500/30 transition-colors">
              <button
                onClick={() => setExpandedCat(expandedCat === cat.key ? null : cat.key)}
                className="w-full flex items-center justify-between p-5 text-left"
              >
                <div className="flex items-center gap-4">
                  <div className="w-10 h-10 rounded-xl bg-emerald-500/10 text-emerald-400 flex items-center justify-center">
                    <Globe className="w-5 h-5" />
                  </div>
                  <div>
                    <h3 className="font-bold text-slate-100">{cat.label}</h3>
                    <p className="text-xs text-slate-500 font-mono">{cat.key} · {cat.domain_count} domain</p>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <span className="px-3 py-1 rounded-full bg-emerald-500/10 text-emerald-300 text-xs font-medium">{cat.domain_count} domain</span>
                  {expandedCat === cat.key ? <ChevronUp className="w-5 h-5 text-slate-400" /> : <ChevronDown className="w-5 h-5 text-slate-400" />}
                </div>
              </button>

              {expandedCat === cat.key && (
                <div className="border-t border-slate-800 p-5 animate-in fade-in slide-in-from-top-1 duration-200">
                  <div className="flex flex-wrap gap-2 mb-5">
                    {cat.domains.map(domain => (
                      <div key={domain} className="group flex items-center gap-2 px-3 py-2 bg-slate-800 rounded-xl border border-slate-700 hover:border-red-500/40 transition-colors">
                        <ExternalLink className="w-3.5 h-3.5 text-slate-500" />
                        <span className="text-sm text-slate-200">{domain}</span>
                        <button onClick={() => handleRemoveDomain(cat.key, domain)} className="text-slate-600 hover:text-red-400 transition-colors ml-1" title="Xóa domain">
                          <X className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    ))}
                  </div>

                  <div className="flex gap-3 items-center">
                    <input
                      type="text" value={newDomain} onChange={e => setNewDomain(e.target.value)}
                      placeholder="Nhập domain mới, vd: gearvn.com"
                      className="flex-1 bg-slate-800 border border-slate-700 rounded-xl px-4 py-2.5 text-sm text-slate-100 placeholder:text-slate-600 outline-none focus:border-emerald-500 transition"
                      onKeyDown={e => { if (e.key === "Enter") handleAddDomain(cat.key); }}
                    />
                    <button onClick={() => handleAddDomain(cat.key)} disabled={actionLoading} className="px-4 py-2.5 bg-emerald-600 hover:bg-emerald-500 text-white text-sm font-medium rounded-xl transition-colors flex items-center gap-2">
                      <Plus className="w-4 h-4" /> Thêm
                    </button>
                  </div>

                  <div className="mt-4 pt-4 border-t border-slate-800/50 flex justify-end">
                    <button onClick={() => handleDeleteCategory(cat.key)} className="text-xs text-slate-500 hover:text-red-400 transition-colors flex items-center gap-1.5">
                      <Trash2 className="w-3.5 h-3.5" /> Xóa toàn bộ danh mục này
                    </button>
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default App;
