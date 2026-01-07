import React from 'react';
import { ChevronDown, Check } from 'lucide-react';

// Card component
export function Card({ children, className = '' }) {
  return (
    <div className={`bg-white rounded-xl shadow-sm border border-gray-100 ${className}`}>
      {children}
    </div>
  );
}

// Button component
export function Button({
  children,
  variant = 'primary',
  size = 'md',
  disabled = false,
  loading = false,
  onClick,
  className = '',
  ...props
}) {
  const variants = {
    primary: 'bg-indigo-600 text-white hover:bg-indigo-700 disabled:bg-gray-300',
    secondary: 'bg-gray-100 text-gray-700 hover:bg-gray-200',
    outline: 'border border-gray-200 text-gray-700 hover:bg-gray-50',
    danger: 'bg-red-600 text-white hover:bg-red-700',
  };

  const sizes = {
    sm: 'px-3 py-1.5 text-sm',
    md: 'px-4 py-2',
    lg: 'px-6 py-3',
  };

  return (
    <button
      onClick={onClick}
      disabled={disabled || loading}
      className={`flex items-center justify-center gap-2 rounded-lg font-medium transition-all ${variants[variant]} ${sizes[size]} ${className} disabled:cursor-not-allowed`}
      {...props}
    >
      {loading && (
        <div className="w-4 h-4 border-2 border-current border-t-transparent rounded-full animate-spin" />
      )}
      {children}
    </button>
  );
}

// Dropdown component
export function Dropdown({
  label,
  value,
  options,
  onChange,
  placeholder = 'Select...',
  className = '',
}) {
  const [isOpen, setIsOpen] = React.useState(false);

  const selectedOption = options.find(
    (opt) => opt.value === value || opt.key === value
  );

  return (
    <div className={`relative ${className}`}>
      {label && (
        <label className="block text-sm text-gray-500 mb-2">{label}</label>
      )}
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className="w-full flex items-center justify-between px-4 py-3 bg-white border border-gray-200 rounded-lg hover:border-indigo-300 transition-colors text-left"
      >
        <span className={selectedOption ? 'text-gray-800' : 'text-gray-400'}>
          {selectedOption?.label || selectedOption?.name || placeholder}
        </span>
        <ChevronDown
          size={18}
          className={`text-gray-400 transition-transform ${isOpen ? 'rotate-180' : ''}`}
        />
      </button>
      {isOpen && (
        <>
          <div
            className="fixed inset-0 z-10"
            onClick={() => setIsOpen(false)}
          />
          <div className="absolute z-20 w-full mt-2 bg-white border border-gray-200 rounded-lg shadow-lg overflow-hidden max-h-60 overflow-y-auto">
            {options.map((option) => (
              <button
                key={option.value || option.key || option.id}
                onClick={() => {
                  onChange(option.value || option.key || option.id);
                  setIsOpen(false);
                }}
                className="w-full flex items-center justify-between px-4 py-3 hover:bg-gray-50 transition-colors"
              >
                <span className="text-gray-700">
                  {option.label || option.name}
                </span>
                {(option.value === value || option.key === value) && (
                  <Check size={16} className="text-indigo-600" />
                )}
              </button>
            ))}
          </div>
        </>
      )}
    </div>
  );
}

// DateInput component
export function DateInput({ label, value, onChange, className = '' }) {
  return (
    <div className={className}>
      {label && (
        <label className="block text-sm text-gray-500 mb-2">{label}</label>
      )}
      <input
        type="date"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full px-4 py-3 bg-gray-50 border border-gray-200 rounded-lg outline-none focus:border-indigo-300 text-gray-700"
      />
    </div>
  );
}

// MetricCard component
export function MetricCard({ icon: Icon, label, value, subValue, color }) {
  return (
    <div className="bg-white rounded-xl p-5 shadow-sm border border-gray-100">
      <div className="flex items-center gap-3 mb-3">
        <div className={`p-2 rounded-lg ${color}`}>
          <Icon size={20} className="text-white" />
        </div>
        <span className="text-gray-500 text-sm">{label}</span>
      </div>
      <div className="text-2xl font-bold text-gray-800">{value}</div>
      {subValue && (
        <div className="text-sm text-gray-400 mt-1">{subValue}</div>
      )}
    </div>
  );
}

// Toggle component
export function Toggle({ checked, onChange, label, description }) {
  return (
    <label className="flex items-center justify-between p-4 bg-gray-50 rounded-lg cursor-pointer">
      <div>
        <p className="text-sm font-medium text-gray-700">{label}</p>
        {description && (
          <p className="text-xs text-gray-400">{description}</p>
        )}
      </div>
      <div className="relative">
        <input
          type="checkbox"
          checked={checked}
          onChange={(e) => onChange(e.target.checked)}
          className="sr-only peer"
        />
        <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-indigo-600"></div>
      </div>
    </label>
  );
}

// Alert component
export function Alert({ type = 'info', children, className = '' }) {
  const types = {
    info: 'bg-blue-50 text-blue-700 border-blue-200',
    success: 'bg-green-50 text-green-700 border-green-200',
    warning: 'bg-yellow-50 text-yellow-700 border-yellow-200',
    error: 'bg-red-50 text-red-700 border-red-200',
  };

  return (
    <div className={`p-4 rounded-lg border ${types[type]} ${className}`}>
      {children}
    </div>
  );
}
