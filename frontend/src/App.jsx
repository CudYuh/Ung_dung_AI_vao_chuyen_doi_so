import { useState, useEffect } from 'react'
import axios from 'axios'
import { Search, Package, Cpu, Loader2, AlertCircle, Sparkles, Globe, Database, ChevronDown, ChevronUp, ArrowLeft, Download, CheckCircle, FileText } from 'lucide-react'

const API_BASE_URL = 'http://localhost:8000'

function App() {
  const [query, setQuery] = useState('')
  const [products, setProducts] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  // AI Valuation state
  const [aiLoading, setAiLoading] = useState(false)
  const [aiResult, setAiResult] = useState(null)
  const [aiError, setAiError] = useState(null)
  const [showRawData, setShowRawData] = useState(false)

  // Approve price state
  const [approving, setApproving] = useState(false)
  const [approveSuccess, setApproveSuccess] = useState(null)
  const [approvedProductData, setApprovedProductData] = useState(null)

  const searchProducts = async (searchQuery) => {
    if (!searchQuery.trim()) {
      setProducts([])
      setAiResult(null)
      setAiError(null)
      return
    }

    setLoading(true)
    setError(null)
    setAiResult(null)
    setAiError(null)

    try {
      const response = await axios.get(`${API_BASE_URL}/products/search`, {
        params: { q: searchQuery }
      })
      setProducts(response.data)
    } catch (err) {
      console.error('Error fetching products:', err)
      setError('Không thể kết nối với server. Vui lòng thử lại sau.')
    } finally {
      setLoading(false)
    }
  }

  const askAI = async () => {
    if (!query.trim()) return
    setAiLoading(true)
    setAiResult(null)
    setAiError(null)

    try {
      const response = await axios.post(`${API_BASE_URL}/api/v1/valuate`, {
        product_name: query
      })
      const data = response.data
      if (data.status === 'error') {
        setAiError(data.error || 'AI gặp lỗi khi xử lý.')
      } else {
        setAiResult(data)
        setApproveSuccess(null)
      }
    } catch (err) {
      console.error('AI error:', err)
      setAiError('Không thể kết nối với AI. Vui lòng thử lại.')
    } finally {
      setAiLoading(false)
    }
  }

  const approvePrice = async (price, source, specs) => {
    setApproving(true)
    setApproveSuccess(null)
    try {
      const response = await axios.post(`${API_BASE_URL}/products/approve`, {
        name: aiResult?.product || query,
        price: String(price),
        source: source || 'N/A',
        specifications: specs || 'Theo kết quả AI'
      })
      if (response.data.status === 'success') {
        setApproveSuccess('Đã phê duyệt giá và lưu vào cơ sở dữ liệu!')
        setApprovedProductData(response.data.data)
        searchProducts(query) // Refresh the products list
      }
    } catch (err) {
      console.error('Lỗi khi phê duyệt giá:', err)
      alert('Có lỗi xảy ra khi phê duyệt giá.')
    } finally {
      setApproving(false)
    }
  }

  // Debounce search
  useEffect(() => {
    const timeOutId = setTimeout(() => {
      searchProducts(query)
    }, 500)
    return () => clearTimeout(timeOutId)
  }, [query])

  // Nếu đã phê duyệt xong, hiển thị màn hình Chi tiết / In PDF
  if (approvedProductData) {
    const product = approvedProductData;
    return (
      <div className="min-h-screen bg-slate-950 text-slate-50 font-sans p-4 md:p-8 print:bg-white print:text-black print:p-0">
        {/* Nút thao tác (ẩn khi in) */}
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

        {/* Nội dung chứng thư (sẽ được in) */}
        <div className="max-w-4xl mx-auto bg-slate-900 border border-slate-800 rounded-2xl p-8 md:p-12 print:bg-white print:border-none print:shadow-none print:p-8 print:w-[100%] print:max-w-none">
          <div className="text-center mb-10 border-b border-slate-800 pb-8 print:border-gray-300">
            <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-emerald-500/10 text-emerald-400 mb-4 print:text-black print:bg-transparent">
              <CheckCircle className="w-10 h-10" />
            </div>
            <h1 className="text-3xl font-bold text-slate-100 print:text-black mb-2 uppercase tracking-wide">Chứng Thư Phê Duyệt Giá</h1>
            <p className="text-slate-500 print:text-gray-600 font-mono">Số: {product.certificate_number || 'N/A'}</p>
          </div>

          <div className="space-y-6 text-sm md:text-base">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-2 md:gap-4 border-b border-slate-800/50 pb-6 print:border-gray-300 print:grid-cols-3">
              <div className="text-slate-400 print:text-gray-600 font-medium">Tên tài sản:</div>
              <div className="md:col-span-2 font-bold text-lg text-slate-100 print:text-black">{product.name}</div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-2 md:gap-4 border-b border-slate-800/50 pb-6 print:border-gray-300 print:grid-cols-3">
              <div className="text-slate-400 print:text-gray-600 font-medium">Loại tài sản:</div>
              <div className="md:col-span-2 text-slate-300 print:text-black">{product.category || 'Tài sản định giá'}</div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-2 md:gap-4 border-b border-slate-800/50 pb-6 print:border-gray-300 print:grid-cols-3">
              <div className="text-slate-400 print:text-gray-600 font-medium">Đơn vị tính:</div>
              <div className="md:col-span-2 text-slate-300 print:text-black">{product.unit || 'Cái'}</div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-2 md:gap-4 border-b border-slate-800/50 pb-6 print:border-gray-300 print:grid-cols-3">
              <div className="text-slate-400 print:text-gray-600 font-medium">Thông số kỹ thuật / Căn cứ:</div>
              <div className="md:col-span-2 text-slate-300 print:text-black whitespace-pre-wrap">{product.specifications || 'N/A'}</div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-2 md:gap-4 border-b border-slate-800/50 pb-6 print:border-gray-300 print:grid-cols-3">
              <div className="text-slate-400 print:text-gray-600 font-medium">Nguồn tham khảo:</div>
              <div className="md:col-span-2 text-blue-400 print:text-blue-600 break-words">{product.source || 'N/A'}</div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-2 md:gap-4 border-b border-slate-800/50 pb-6 print:border-gray-300 print:grid-cols-3">
              <div className="text-slate-400 print:text-gray-600 font-medium flex items-center h-full">Giá phê duyệt:</div>
              <div className="md:col-span-2 text-2xl font-bold text-emerald-400 print:text-black">
                {product.price} {String(product.price).toLowerCase().includes('vnd') ? '' : 'VND'}
              </div>
            </div>

            <div className="grid grid-cols-2 gap-8 pt-8 text-center print:pt-16">
              <div className="flex flex-col items-center">
                <p className="font-medium mb-16 text-slate-300 print:text-black">Người yêu cầu</p>
                <p className="text-slate-500 print:text-gray-500 italic">(Ký và ghi rõ họ tên)</p>
              </div>
              <div className="flex flex-col items-center">
                <p className="mb-2 text-slate-400 print:text-gray-600">Ngày {(product.appraisal_date || '').split('/')[0] || '...'} tháng {(product.appraisal_date || '').split('/')[1] || '...'} năm {(product.appraisal_date || '').split('/')[2] || '2026'}</p>
                <p className="font-medium mb-16 text-slate-300 print:text-black">Người phê duyệt </p>
                <p className="text-slate-500 print:text-gray-500 italic">(Ký và ghi rõ họ tên)</p>
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  }

  const noDbResults = !loading && query && products.length === 0 && !error

  return (
    <div className="min-h-screen bg-slate-950 text-slate-50 font-sans selection:bg-blue-500/30">
      {/* Hero Section */}
      <header className="relative overflow-hidden pt-16 pb-12 px-4">
        <div className="absolute top-0 left-1/2 -translate-x-1/2 w-full max-w-6xl h-full opacity-20 pointer-events-none">
          <div className="absolute top-[-10%] left-[-10%] w-[40%] h-[40%] bg-blue-600 rounded-full blur-[120px]"></div>
          <div className="absolute bottom-[10%] right-[-5%] w-[30%] h-[30%] bg-indigo-600 rounded-full blur-[100px]"></div>
        </div>

        <div className="relative max-w-4xl mx-auto text-center">
          <h1 className="text-4xl md:text-6xl font-extrabold tracking-tight mb-4 bg-gradient-to-r from-blue-400 to-indigo-400 bg-clip-text text-transparent">
            Tìm Kiếm Sản Phẩm
          </h1>
          <p className="text-lg text-slate-400 mb-8 max-w-2xl mx-auto">
            Tra cứu thông tin sản phẩm và thông số kỹ thuật nhanh chóng từ hệ thống dữ liệu thông minh.
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
              {loading && <Loader2 className="w-6 h-6 text-blue-500 animate-spin" />}
            </div>
          </div>
        </div>
      </header>

      {/* Results Section */}
      <main className="max-w-6xl mx-auto px-4 pb-24">
        {error && (
          <div className="flex items-center gap-3 p-4 bg-red-500/10 border border-red-500/20 rounded-xl text-red-400 mb-8">
            <AlertCircle className="w-5 h-5 shrink-0" />
            <p>{error}</p>
          </div>
        )}

        {/* DB Results */}
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
                    <div className="flex items-center gap-2 mb-0.5">
                      <Database className="w-3 h-3 text-emerald-400" />
                      <span className="text-xs font-medium text-emerald-400 uppercase tracking-wider">Database nội bộ</span>
                    </div>
                    <h3 className="text-xl font-bold text-slate-100 line-clamp-1">
                      {product.name}
                    </h3>
                  </div>
                </div>
                <span className="text-xs font-mono text-slate-600">STT: #{product.id}</span>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mt-4">
                <div className="space-y-3">
                  <div className="flex items-start gap-2">
                    <Cpu className="w-4 h-4 text-slate-500 shrink-0 mt-0.5" />
                    <div className="text-sm text-slate-400">
                      <span className="text-slate-500 font-medium block">Thông số kỹ thuật:</span>
                      <span className="line-clamp-3">{product.specifications || 'N/A'}</span>
                    </div>
                  </div>
                  <div className="text-sm text-slate-400">
                    <span className="text-slate-500 font-medium">Đơn vị tính: </span>
                    {product.unit || 'N/A'}
                  </div>
                </div>

                <div className="space-y-3 border-l border-slate-800/50 pl-4">
                  <div className="text-sm">
                    <span className="text-slate-500 font-medium block">Giá thẩm định:</span>
                    <span className="text-blue-400 font-bold text-lg">{product.price ? `${product.price} VND` : 'Liên hệ'}</span>
                  </div>
                  <div className="text-xs text-slate-500 space-y-1">
                    <p><span className="font-medium">Số chứng thư:</span> {product.certificate_number || 'N/A'}</p>
                    <p><span className="font-medium">Ngày thẩm định:</span> {product.appraisal_date || 'N/A'}</p>
                  </div>
                </div>
              </div>

              <div className="mt-4 pt-4 border-t border-slate-800/50 flex flex-wrap justify-between items-center gap-2">
                <div className="text-xs text-slate-500">
                  <span className="font-medium text-slate-600">Nguồn:</span> {product.source || 'N/A'}
                </div>
                <div className="text-xs text-slate-500">
                  <span className="font-medium text-slate-600">Người thẩm định:</span> {product.appraiser || 'N/A'}
                </div>
              </div>

              <div className="absolute bottom-0 left-0 w-full h-1 bg-gradient-to-r from-blue-600 to-indigo-600 scale-x-0 group-hover:scale-x-100 transition-transform duration-500 origin-left rounded-b-2xl"></div>
            </div>
          ))}
        </div>

        {/* ===== KHI KHÔNG CÓ KẾT QUẢ TRONG DB → HIỆN NÚT GỌI AI ===== */}
        {noDbResults && !aiResult && (
          <div className="text-center py-16 animate-in fade-in duration-500">
            <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-slate-900 border border-slate-800 mb-4">
              <Package className="w-8 h-8 text-slate-600" />
            </div>
            <p className="text-slate-500 text-lg mb-2">
              Không tìm thấy <span className="text-slate-300 font-semibold">"{query}"</span> trong Database nội bộ.
            </p>
            <p className="text-slate-600 text-sm mb-8">
              Hãy để AI tìm kiếm thông tin giá cả trên Internet cho bạn.
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

        {/* ===== HIỂN THỊ KẾT QUẢ AI ===== */}
        {aiLoading && (
          <div className="mt-6 p-6 bg-violet-500/5 border border-violet-500/20 rounded-2xl text-center">
            <Loader2 className="w-8 h-8 text-violet-400 animate-spin mx-auto mb-3" />
            <p className="text-violet-300 font-medium">AI đang tìm kiếm thông tin trên Internet...</p>
            <p className="text-slate-500 text-sm mt-1">Quá trình này có thể mất 10–30 giây</p>
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
            {/* Header badge */}
            <div className="flex items-center gap-2 mb-4">
              <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-violet-500/10 border border-violet-500/30 text-violet-300 text-xs font-medium">
                <Globe className="w-3.5 h-3.5" />
                Kết quả từ AI + Internet (Tavily)
              </div>
              <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-slate-800 text-slate-400 text-xs">
                <Sparkles className="w-3.5 h-3.5 text-amber-400" />
                Groq LLaMA 3.3
              </div>
            </div>

            {/* AI Result Card */}
            <div className="relative bg-slate-900/70 border border-violet-500/30 rounded-2xl overflow-hidden shadow-[0_0_40px_-10px_rgba(124,58,237,0.3)]">
              {/* Glow bar top */}
              <div className="h-1 w-full bg-gradient-to-r from-violet-600 via-indigo-500 to-blue-600"></div>

              <div className="p-6">
                <div className="flex items-center gap-3 mb-5">
                  <div className="w-10 h-10 rounded-xl bg-violet-500/10 flex items-center justify-center">
                    <Sparkles className="w-5 h-5 text-violet-400" />
                  </div>
                  <div>
                    <h3 className="font-bold text-slate-100">Kết quả định giá AI</h3>
                    <p className="text-xs text-slate-500">Sản phẩm: {aiResult.product}</p>
                  </div>
                </div>

                {/* AI Response */}
                <div className="prose prose-invert prose-sm max-w-none">
                  {(() => {
                    const result = aiResult.valuation_result;
                    if (!result) return null;

                    if (typeof result === 'string') {
                      const urlRegex = /(https?:\/\/[^\s]+)/g;
                      const parts = result.split(urlRegex);
                      return (
                        <div className="bg-slate-800/50 rounded-xl p-5 border border-slate-700/50">
                          <div className="text-slate-200 leading-relaxed whitespace-pre-wrap text-sm">
                            {parts.map((part, index) => {
                              if (part.match(urlRegex)) {
                                return (
                                  <a key={index} href={part} target="_blank" rel="noopener noreferrer" className="text-blue-400 hover:text-blue-300 underline font-medium">
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
                        {/* Final Price */}
                        <div className="bg-gradient-to-r from-violet-600/20 to-indigo-600/20 rounded-xl p-5 border border-violet-500/30">
                          <h4 className="text-violet-300 font-semibold mb-2">Giá chốt dự kiến:</h4>
                          <div className="flex items-center justify-between flex-wrap gap-4">
                            <span className="text-2xl font-bold text-white">{result.final_price} {String(result.final_price).toLowerCase().includes('vnd') ? '' : 'VND'}</span>
                            <button
                              onClick={() => approvePrice(result.final_price, 'AI Valuation', result.basis)}
                              disabled={approving}
                              className="px-4 py-2 bg-violet-600 hover:bg-violet-500 text-white text-sm font-medium rounded-lg transition-colors flex items-center gap-2"
                            >
                              {approving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Database className="w-4 h-4" />}
                              Phê duyệt giá này
                            </button>
                          </div>
                          <p className="text-sm text-slate-300 mt-3"><span className="text-slate-400">Căn cứ:</span> {result.basis}</p>
                          <div className="flex items-center gap-2 mt-3 text-xs">
                            <span className={`px-2 py-1 rounded bg-slate-800 ${result.confidence === 'cao' ? 'text-emerald-400' : result.confidence === 'trung bình' ? 'text-amber-400' : 'text-red-400'}`}>
                              Độ tin cậy: {result.confidence}
                            </span>
                            <span className="text-slate-500">{result.reason}</span>
                          </div>
                        </div>

                        {/* References */}
                        {result.reference_quotes && result.reference_quotes.length > 0 && (
                          <div>
                            <h4 className="text-slate-400 text-sm font-medium mb-3 uppercase tracking-wider">Các báo giá tham khảo:</h4>
                            <div className="grid grid-cols-1 gap-4">
                              {result.reference_quotes.map((quote, idx) => (
                                <div key={idx} className="bg-slate-800/50 rounded-xl p-4 border border-slate-700/50 flex flex-col sm:flex-row gap-4 justify-between">
                                  <div className="space-y-2 flex-1">
                                    <p className="text-slate-200 font-medium text-sm">{quote.description}</p>
                                    <p className="text-blue-400 font-bold">{quote.price} {String(quote.price).toLowerCase().includes('vnd') ? '' : 'VND'}</p>
                                    {quote.url && (
                                      <a href={quote.url} target="_blank" rel="noopener noreferrer" className="text-xs text-violet-400 hover:underline inline-flex items-center gap-1">
                                        <Globe className="w-3 h-3" /> Nguồn tham khảo
                                      </a>
                                    )}
                                  </div>
                                  <div className="flex items-center shrink-0">
                                    <button
                                      onClick={() => approvePrice(quote.price, quote.url || 'Internet', quote.description)}
                                      disabled={approving}
                                      className="px-3 py-1.5 bg-slate-700 hover:bg-slate-600 text-white text-xs font-medium rounded-lg transition-colors flex items-center gap-2"
                                    >
                                      {approving ? <Loader2 className="w-3 h-3 animate-spin" /> : <Database className="w-3 h-3" />}
                                      Phê duyệt giá
                                    </button>
                                  </div>
                                </div>
                              ))}
                            </div>
                          </div>
                        )}

                        {approveSuccess && (
                          <div className="p-3 bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 rounded-lg text-sm flex items-center gap-2 mt-4">
                            <Sparkles className="w-4 h-4" />
                            {approveSuccess}
                          </div>
                        )}
                      </div>
                    );
                  })()}
                </div>

                {/* Raw data toggle */}
                {aiResult.raw_data && (
                  <div className="mt-4">
                    <button
                      onClick={() => setShowRawData(!showRawData)}
                      className="flex items-center gap-2 text-xs text-slate-500 hover:text-slate-300 transition-colors"
                    >
                      {showRawData ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                      {showRawData ? 'Ẩn' : 'Xem'} dữ liệu thu thập từ Internet
                    </button>
                    {showRawData && (
                      <div className="mt-3 p-4 bg-slate-950 rounded-xl border border-slate-800 text-xs text-slate-400 font-mono whitespace-pre-wrap max-h-64 overflow-y-auto">
                        {aiResult.raw_data}
                      </div>
                    )}
                  </div>
                )}

                {/* Disclaimer */}
                <div className="mt-5 flex items-start gap-2 p-3 bg-amber-500/5 border border-amber-500/20 rounded-lg">
                  <AlertCircle className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
                  <p className="text-xs text-amber-300/80">
                    Kết quả mang tính tham khảo, được tổng hợp từ dữ liệu Internet. Nên xác minh lại với chuyên gia trước khi đưa ra quyết định.
                  </p>
                </div>
              </div>
            </div>

            {/* Try again button */}
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

        {/* Empty state - no query */}
        {!query && (
          <div className="text-center py-20">
            <div className="inline-flex items-center justify-center w-20 h-20 rounded-full bg-slate-900/50 border border-slate-800 mb-6 text-slate-700">
              <Search className="w-10 h-10" />
            </div>
            <h2 className="text-2xl font-semibold text-slate-400 mb-2">Bắt đầu tìm kiếm</h2>
            <p className="text-slate-500">Hãy nhập tên hoặc thông số sản phẩm bạn muốn tìm vào thanh tìm kiếm bên trên.</p>
            <div className="mt-6 flex items-center justify-center gap-6 text-xs text-slate-600">
              <span className="flex items-center gap-1.5"><Database className="w-3.5 h-3.5 text-emerald-600" /> Tìm trong Database nội bộ</span>
              <span className="text-slate-700">→</span>
              <span className="flex items-center gap-1.5"><Globe className="w-3.5 h-3.5 text-violet-600" /> Nếu không có, AI tìm trên Internet</span>
            </div>
          </div>
        )}
      </main>

      {/* Footer */}
      <footer className="border-t border-slate-900 py-8 px-4 text-center">
        <p className="text-slate-600 text-sm">
          &copy; 2026 AI Application. Hệ thống tra cứu sản phẩm thông minh.
        </p>
      </footer>
    </div>
  )
}

export default App
