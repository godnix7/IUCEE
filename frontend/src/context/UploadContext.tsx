import React, { createContext, useContext, useState } from 'react';
import type { ReactNode } from 'react';

interface UploadContextType {
  files: File[];
  setFiles: React.Dispatch<React.SetStateAction<File[]>>;
  populationCount: number | '';
  setPopulationCount: React.Dispatch<React.SetStateAction<number | ''>>;
  populationSource: string;
  setPopulationSource: React.Dispatch<React.SetStateAction<string>>;
  populationDate: string;
  setPopulationDate: React.Dispatch<React.SetStateAction<string>>;
  selectedProjectId: number | null;
  setSelectedProjectId: React.Dispatch<React.SetStateAction<number | null>>;
  analysisMode: 'segmentation' | 'detection' | 'scene_segmentation';
  setAnalysisMode: React.Dispatch<React.SetStateAction<'segmentation' | 'detection' | 'scene_segmentation'>>;
  clearUploadQueue: () => void;
}

const UploadContext = createContext<UploadContextType | undefined>(undefined);

export const UploadProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [files, setFiles] = useState<File[]>([]);
  const [populationCount, setPopulationCount] = useState<number | ''>('');
  const [populationSource, setPopulationSource] = useState('user_supplied');
  const [populationDate, setPopulationDate] = useState(new Date().toISOString().split('T')[0]);
  const [selectedProjectId, setSelectedProjectId] = useState<number | null>(() => {
    const saved = sessionStorage.getItem('selectedProjectId');
    return saved ? Number(saved) : null;
  });
  const [analysisMode, setAnalysisMode] = useState<'segmentation' | 'detection' | 'scene_segmentation'>(() => {
    const saved = sessionStorage.getItem('analysisMode');
    if (saved === 'detection' || saved === 'scene_segmentation') return saved;
    return 'segmentation';
  });

  React.useEffect(() => {
    sessionStorage.setItem('analysisMode', analysisMode);
  }, [analysisMode]);

  // Keep sessionStorage in sync
  React.useEffect(() => {
    if (selectedProjectId) sessionStorage.setItem('selectedProjectId', selectedProjectId.toString());
  }, [selectedProjectId]);

  const clearUploadQueue = () => {
    setFiles([]);
    setPopulationCount('');
  };

  return (
    <UploadContext.Provider value={{
      files, setFiles,
      populationCount, setPopulationCount,
      populationSource, setPopulationSource,
      populationDate, setPopulationDate,
      selectedProjectId, setSelectedProjectId,
      analysisMode, setAnalysisMode,
      clearUploadQueue
    }}>
      {children}
    </UploadContext.Provider>
  );
};

export const useUploadQueue = () => {
  const context = useContext(UploadContext);
  if (context === undefined) {
    throw new Error('useUploadQueue must be used within an UploadProvider');
  }
  return context;
};
