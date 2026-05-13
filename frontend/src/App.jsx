import { useState, useEffect } from 'react'
import axios from 'axios'
import { Search, Package, Cpu, Loader2, AlertCircle } from 'lucide-react'

const API_BASE_URL = 'http://localhost:8000'

function App() {
  const [query, setQuery] = useState('')
  const [products, setProducts] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const searchProducts = async (searchQuery) => {
    if (!searchQuery.trim()) {
      setProducts([])
      return
    }

    setLoading(true)
    setError(null)
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

  // Debounce search
  useEffect(() => {
    const timeOutId = setTimeout(() => {
      searchProducts(query)
    }, 500)
    return () => clearTimeout(timeOutId)
  }, [query])

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
          <div className="flex items-center gap-3 p-4 bg-red-500/10 border border-red-500/20 rounded-xl text-red-400 mb-8 animate-in fade-in slide-in-from-top-4 duration-300">
            <AlertCircle className="w-5 h-5 shrink-0" />
            <p>{error}</p>
          </div>
        )}

        {!loading && query && products.length === 0 && !error && (
          <div className="text-center py-20 animate-in fade-in duration-500">
            <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-slate-900 border border-slate-800 mb-4">
              <Package className="w-8 h-8 text-slate-600" />
            </div>
            <p className="text-slate-500 text-lg">Không tìm thấy sản phẩm nào khớp với từ khóa của bạn.</p>
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
                    <span className="text-xs font-medium text-blue-400 uppercase tracking-wider">{product.category || 'Hàng hóa'}</span>
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

        {!query && (
          <div className="text-center py-20">
            <div className="inline-flex items-center justify-center w-20 h-20 rounded-full bg-slate-900/50 border border-slate-800 mb-6 text-slate-700">
              <Search className="w-10 h-10" />
            </div>
            <h2 className="text-2xl font-semibold text-slate-400 mb-2">Bắt đầu tìm kiếm</h2>
            <p className="text-slate-500">Hãy nhập tên hoặc thông số sản phẩm bạn muốn tìm vào thanh tìm kiếm bên trên.</p>
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
