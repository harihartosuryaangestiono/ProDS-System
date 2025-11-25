import { Info, User, GraduationCap, BookOpen, Heart, Code, Sparkles } from 'lucide-react';
import Layout from '../components/Layout';

const About = () => {
  // Data About - Informasi Pembuat Website, Dosen, dan Mata Kuliah
  const aboutData = {
    developers: [
      {
        name: "Rayhan Adji Santoso",
        role: "Mahasiswa",
        description: "NPM: 6182101017"
      },
      {
        name: "Hariharto Surya Angestiono",
        role: "Mahasiswa",
        description: "NPM: 6182101045"
      },
      {
        name: "Anggra Muhammad Razi",
        role: "Mahasiswa",
        description: "NPM: 6182101059"
      },
      {
        name: "Kenzhu Matthew",
        role: "Mahasiswa",
        description: "NPM: 6182101063"
      }
    ],
    lecturers: [
      {
        name: "Prof. Dr. Veronica Sri Moertini, Ir., M.T.",
        role: "Dosen Pembimbing",
        description: "Dosen yang membimbing pengembangan sistem ini"
      },
      {
        name: "Kristopher David Harjono S.Kom., M.T.",
        role: "Dosen Pembimbing",
        description: "Dosen yang membimbing pengembangan sistem ini"
      }
    ],
    course: {
      name: "Proyek Data Science 2",
      code: "AIF234401-03",
      description: "Mata kuliah yang menjadi konteks pengembangan sistem ini"
    }
  };

  return (
    <Layout
      bgColor="bg-gradient-to-br from-blue-50 via-indigo-50 to-purple-50"
      maxWidth="max-w-7xl"
      showHeader={false}
      className="py-12"
    >
        {/* Header Section */}
        <div className="text-center mb-12 animate-fade-in w-full">
          <div className="inline-flex items-center justify-center w-20 h-20 bg-gradient-to-br from-blue-500 to-indigo-600 rounded-2xl shadow-xl mb-6 transform hover:scale-110 transition-transform duration-300">
            <Info className="h-10 w-10 text-white" />
          </div>
          <h1 className="text-3xl sm:text-4xl md:text-5xl lg:text-6xl font-bold bg-gradient-to-r from-blue-600 via-indigo-600 to-purple-600 bg-clip-text text-transparent mb-4 w-full overflow-visible whitespace-normal">
            Tentang Sistem
          </h1>
          <p className="text-base sm:text-lg md:text-xl text-gray-600 max-w-3xl mx-auto w-full overflow-visible whitespace-normal leading-relaxed">
            Sistem Manajemen Data Publikasi dan Dosen berbasis SINTA dan Google Scholar
          </p>
        </div>

        {/* Main Content Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8 mb-12">
          {/* Developers Card */}
          <div className="lg:col-span-1">
            <div className="bg-white rounded-2xl shadow-xl p-8 h-full transform hover:scale-105 transition-all duration-300 border border-gray-100">
              <div className="flex items-center justify-center w-16 h-16 bg-gradient-to-br from-blue-500 to-blue-600 rounded-xl mb-6 mx-auto shadow-lg">
                <Code className="h-8 w-8 text-white" />
              </div>
              <h2 className="text-2xl font-bold text-gray-900 text-center mb-6 flex items-center justify-center gap-2">
                <User className="h-6 w-6 text-blue-600" />
                Pembuat Website
              </h2>
              <div className="space-y-4">
                {aboutData.developers.map((developer, index) => (
                  <div
                    key={index}
                    className="bg-gradient-to-br from-blue-50 to-indigo-50 rounded-xl p-6 border border-blue-100 hover:shadow-md transition-shadow duration-300"
                  >
                    <div className="flex items-start space-x-4">
                      <div className="flex-shrink-0">
                        <div className="w-12 h-12 bg-gradient-to-br from-blue-500 to-indigo-600 rounded-full flex items-center justify-center shadow-md">
                          <User className="h-6 w-6 text-white" />
                        </div>
                      </div>
                      <div className="flex-1">
                        <h3 className="text-lg font-semibold text-gray-900 mb-1">
                          {developer.name}
                        </h3>
                        <p className="text-sm font-medium text-blue-600 mb-2">
                          {developer.role}
                        </p>
                        <p className="text-sm text-gray-600">
                          {developer.description}
                        </p>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Lecturers Card */}
          <div className="lg:col-span-1">
            <div className="bg-white rounded-2xl shadow-xl p-8 h-full transform hover:scale-105 transition-all duration-300 border border-gray-100">
              <div className="flex items-center justify-center w-16 h-16 bg-gradient-to-br from-indigo-500 to-purple-600 rounded-xl mb-6 mx-auto shadow-lg">
                <GraduationCap className="h-8 w-8 text-white" />
              </div>
              <h2 className="text-2xl font-bold text-gray-900 text-center mb-6 flex items-center justify-center gap-2">
                <GraduationCap className="h-6 w-6 text-indigo-600" />
                Dosen Pengajar
              </h2>
              <div className="space-y-4">
                {aboutData.lecturers.map((lecturer, index) => (
                  <div
                    key={index}
                    className="bg-gradient-to-br from-indigo-50 to-purple-50 rounded-xl p-6 border border-indigo-100 hover:shadow-md transition-shadow duration-300"
                  >
                    <div className="flex items-start space-x-4">
                      <div className="flex-shrink-0">
                        <div className="w-12 h-12 bg-gradient-to-br from-indigo-500 to-purple-600 rounded-full flex items-center justify-center shadow-md">
                          <GraduationCap className="h-6 w-6 text-white" />
                        </div>
                      </div>
                      <div className="flex-1">
                        <h3 className="text-lg font-semibold text-gray-900 mb-1">
                          {lecturer.name}
                        </h3>
                        <p className="text-sm font-medium text-indigo-600 mb-2">
                          {lecturer.role}
                        </p>
                        <p className="text-sm text-gray-600">
                          {lecturer.description}
                        </p>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Course Card */}
          <div className="lg:col-span-1">
            <div className="bg-white rounded-2xl shadow-xl p-8 h-full transform hover:scale-105 transition-all duration-300 border border-gray-100">
              <div className="flex items-center justify-center w-16 h-16 bg-gradient-to-br from-purple-500 to-pink-600 rounded-xl mb-6 mx-auto shadow-lg">
                <BookOpen className="h-8 w-8 text-white" />
              </div>
              <h2 className="text-2xl font-bold text-gray-900 text-center mb-6 flex items-center justify-center gap-2">
                <BookOpen className="h-6 w-6 text-purple-600" />
                Mata Kuliah
              </h2>
              <div className="bg-gradient-to-br from-purple-50 to-pink-50 rounded-xl p-6 border border-purple-100 hover:shadow-md transition-shadow duration-300">
                <div className="text-center mb-4">
                  <div className="inline-flex items-center justify-center w-16 h-16 bg-gradient-to-br from-purple-500 to-pink-600 rounded-full mb-4 shadow-md">
                    <BookOpen className="h-8 w-8 text-white" />
                  </div>
                </div>
                <h3 className="text-xl font-bold text-gray-900 mb-2 text-center">
                  {aboutData.course.name}
                </h3>
                <p className="text-sm font-medium text-purple-600 mb-3 text-center">
                  {aboutData.course.code}
                </p>
                <p className="text-sm text-gray-600 text-center">
                  {aboutData.course.description}
                </p>
              </div>
            </div>
          </div>
        </div>
    </Layout>
  );
};

export default About;

